"""Research endpoint boundaries; no trained artifact is required in CI."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app import main as api
from backend.app.config import Settings
from backend.app import scenario_research
from backend.app.simulation import GENERATOR_VERSION, build_mission
from backend.model_evaluation.controlled_live_experiments import matrix
from backend.model_evaluation.experimental_live_features import TelemetryState
from backend.tests.api_auth import authenticate
from backend.app.store import TelemetryStore
from backend.app.schemas import SimulationRequest


def test_production_rejects_synthetic_research_mode(monkeypatch):
    monkeypatch.setenv("DIGITAL_TWIN_ENV", "production")
    monkeypatch.setenv("DIGITAL_TWIN_TOKEN_SECRET", "test-only-secret-with-at-least-thirty-two-characters")
    monkeypatch.setenv("AERION_ENABLE_SCENARIO_RESEARCH", "true")
    with pytest.raises(ValueError, match="synthetic scenario research cannot be enabled"):
        Settings()


def test_research_model_refuses_unvalidated_mission_length_and_sampling():
    with pytest.raises(scenario_research.ScenarioModelError, match="ten-minute mission"):
        scenario_research.predict_saved_synthetic_mission({"duration_seconds": 60, "interval_seconds": 5})
    with pytest.raises(scenario_research.ScenarioModelError, match="every five seconds"):
        scenario_research.predict_saved_synthetic_mission({"duration_seconds": 600, "interval_seconds": 10})


def test_research_model_rejects_corrupt_saved_timestamps(monkeypatch):
    monkeypatch.setattr(scenario_research, "load_scenario_provider",
                        lambda: (None, {"generator_version": GENERATOR_VERSION,
                                        "features": scenario_research.SCENARIO_FEATURES}))
    with pytest.raises(scenario_research.ScenarioModelError, match="timestamps are invalid"):
        scenario_research.predict_saved_synthetic_mission({
            "duration_seconds": 600, "interval_seconds": 5,
            "generator_version": GENERATOR_VERSION, "mission_id": "BAD_TIMESTAMP",
            "telemetry": [{"mission_id": "BAD_TIMESTAMP", "timestamp": "not-a-date"}],
        })


def test_research_endpoint_is_opt_in_and_uses_saved_telemetry(monkeypatch):
    mission_id = f"RESEARCH_{uuid4().hex[:12]}"
    with TestClient(api.app) as client:
        authenticate(client)
        created = client.post("/api/v1/simulations", json={
            "profile": "NORMAL_CRUISE", "degradation_scenario": "MISFIRE",
            "duration_minutes": 1, "interval_seconds": 10,
            "mission_id": mission_id, "seed": 1991,
        })
        assert created.status_code == 200
        url = f"/api/v1/simulations/{mission_id}/research-scenario-diagnostics"
        assert client.get(url).status_code == 503
        seen = []

        def predict(snapshot):
            seen.append(snapshot)
            return {"mission_id": snapshot["mission_id"], "source": "synthetic_scenario_ml_research",
                    "model_sha256": "test-model", "input_sha256": "test-input", "predictions": []}

        monkeypatch.setattr(api, "settings", replace(api.settings, scenario_research_enabled=True))
        monkeypatch.setattr(api, "predict_saved_synthetic_mission", predict)
        response = client.get(url)
        assert response.status_code == 200
        assert response.json()["source"] == "synthetic_scenario_ml_research"
        assert len(seen[0]["telemetry"]) == created.json()["sample_count"]
        assert api.store.save_scenario_predictions(mission_id, "test-model", "test-input", response.json()) == response.json()
        assert client.get("/api/v1/simulations/missing/research-scenario-diagnostics").status_code == 404


def test_checksum_rejected_before_unpickling(tmp_path, monkeypatch):
    artifact = tmp_path / "research_model.joblib"
    artifact.write_bytes(b"not a trusted model")
    (tmp_path / "evaluation.json").write_text(json.dumps({
        "purpose": "synthetic runtime-scenario benchmark only",
        "sklearn_version": __import__("sklearn").__version__,
        "features": scenario_research.SCENARIO_FEATURES,
        "generator_version": GENERATOR_VERSION,
        "simulator_sha256": hashlib.sha256(Path(build_mission.__code__.co_filename).read_bytes()).hexdigest(),
        "offline_features_sha256": hashlib.sha256(Path(matrix.__code__.co_filename).read_bytes()).hexdigest(),
        "streaming_features_sha256": hashlib.sha256(Path(TelemetryState.__init__.__code__.co_filename).read_bytes()).hexdigest(),
        "synthetic_gate_passed": True,
        "artifact_sha256": "0" * 64,
    }), encoding="utf-8")
    monkeypatch.setattr(scenario_research, "TRUSTED_SCENARIO_MODEL_PATH", artifact)
    scenario_research.load_scenario_provider.cache_clear()
    try:
        with pytest.raises(scenario_research.ScenarioModelError, match="checksum differs"):
            scenario_research.load_scenario_provider()
    finally:
        scenario_research.load_scenario_provider.cache_clear()


def test_missing_research_artifact_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(scenario_research, "TRUSTED_SCENARIO_MODEL_PATH", tmp_path / "missing.joblib")
    scenario_research.load_scenario_provider.cache_clear()
    try:
        with pytest.raises(scenario_research.ScenarioModelError, match="missing"):
            scenario_research.load_scenario_provider()
    finally:
        scenario_research.load_scenario_provider.cache_clear()


def test_saved_research_input_rejects_unexpected_and_nonfinite_telemetry(monkeypatch):
    snapshot = build_mission(SimulationRequest(
        profile="NORMAL_CRUISE", duration_minutes=10, interval_seconds=5)).model_dump(mode="json")
    monkeypatch.setattr(scenario_research, "load_scenario_provider", lambda: (
        None, {"generator_version": GENERATOR_VERSION, "features": scenario_research.SCENARIO_FEATURES}))
    snapshot["telemetry"][0]["unknown_feature"] = 1
    with pytest.raises(scenario_research.ScenarioModelError, match="telemetry or timestamps are invalid"):
        scenario_research.predict_saved_synthetic_mission(snapshot)
    del snapshot["telemetry"][0]["unknown_feature"]
    snapshot["telemetry"][0]["rpm"] = float("nan")
    with pytest.raises(scenario_research.ScenarioModelError, match="telemetry is malformed"):
        scenario_research.predict_saved_synthetic_mission(snapshot)


def test_prediction_record_is_atomic_and_versioned(tmp_path):
    store = TelemetryStore(tmp_path / "research.sqlite")
    store.save_simulation("M", "E", "2026-10-11T00:00:00+00:00", 1, {}, {"mission_id": "M"})
    first = {"predictions": [{"scenario_class": "NONE"}]}
    assert store.save_scenario_predictions("M", "model-1", "input-1", first) == first
    assert store.save_scenario_predictions("M", "model-1", "input-1", {"predictions": []}) == first
    assert store.save_scenario_predictions("M", "model-2", "input-1", {"predictions": []}) != first
    with pytest.raises(ValueError, match="Out of range float values"):
        store.save_scenario_predictions("M", "model-3", "input-1", {"score": float("nan")})
    with store._connect() as db:
        assert db.execute("SELECT count(*) FROM scenario_predictions").fetchone()[0] == 2


def test_research_endpoint_handles_prediction_and_persistence_failure(monkeypatch):
    mission_id = f"RESEARCH_FAIL_{uuid4().hex[:10]}"
    with TestClient(api.app) as client:
        authenticate(client)
        assert client.post("/api/v1/simulations", json={"profile": "NORMAL_CRUISE",
            "duration_minutes": 1, "interval_seconds": 10, "mission_id": mission_id}).status_code == 200
        monkeypatch.setattr(api, "settings", replace(api.settings, scenario_research_enabled=True))
        url = f"/api/v1/simulations/{mission_id}/research-scenario-diagnostics"
        def fail_prediction(_):
            raise scenario_research.ScenarioModelError("test prediction failed")
        monkeypatch.setattr(api, "predict_saved_synthetic_mission", fail_prediction)
        assert client.get(url).status_code == 503
        monkeypatch.setattr(api, "predict_saved_synthetic_mission", lambda _: {
            "model_sha256": "test", "input_sha256": "test", "predictions": []})
        def fail_write(*_):
            raise OSError("test database unavailable")
        monkeypatch.setattr(api.store, "save_scenario_predictions", fail_write)
        response = client.get(url)
        assert response.status_code == 503
        assert response.json()["detail"] == "synthetic scenario prediction could not be persisted"
