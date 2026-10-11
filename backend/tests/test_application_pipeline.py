"""Foundation and research-mode contract checks using isolated state."""
from dataclasses import replace
from datetime import timedelta
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import app
from backend.app.ml_diagnostics import TRUSTED_MODEL_SHA256, ArtifactMLProvider, ModelCompatibilityError
from backend.app.ml_features import NUMERIC_FEATURES
from backend.app.store import TelemetryStore
from backend.tests.api_auth import authenticate
from backend.tests.test_diagnostics import BASE, sample
from backend.tests.test_ml_diagnostics import ControlledEstimator, metadata


def test_settings_validate_history_limit_and_default_ml(monkeypatch):
    monkeypatch.delenv("AERION_ENABLE_ML_DIAGNOSTICS", raising=False)
    monkeypatch.delenv("DIGITAL_TWIN_ML_ENABLED", raising=False)
    assert Settings().ml_enabled is False
    monkeypatch.setenv("DIGITAL_TWIN_HISTORY_LIMIT", "0")
    with pytest.raises(ValueError, match="HISTORY_LIMIT"):
        Settings()


def test_store_migrates_legacy_without_losing_rows_and_rejects_future_schema(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE telemetry (id INTEGER PRIMARY KEY, engine_id TEXT NOT NULL, mission_id TEXT NOT NULL, timestamp TEXT NOT NULL, telemetry_json TEXT NOT NULL, assessment_json TEXT NOT NULL)")
        db.execute("INSERT INTO telemetry(engine_id,mission_id,timestamp,telemetry_json,assessment_json) VALUES(?,?,?,?,?)", ("E", "M", "2026-01-01T00:00:00+00:00", "{}", "{}"))
    store = TelemetryStore(path)
    assert store.ready()
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 3
        assert db.execute("SELECT count(*) FROM telemetry").fetchone()[0] == 1
        assert "state_json" in {row[1] for row in db.execute("PRAGMA table_info(telemetry)")}
        assert "simulation_snapshots" in {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        db.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="newer"):
        TelemetryStore(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT count(*) FROM telemetry").fetchone()[0] == 1


def test_readiness_and_persisted_fallback_contract():
    with TestClient(app) as client:
        ready = client.get("/api/v1/ready")
        assert ready.status_code == 200
        assert ready.json()["database"] == "ready"
        assert ready.json()["ml_status"] == "disabled"
        authenticate(client)
        telemetry = sample(engine_id="PIPELINE_TEST", mission_id="PIPELINE_MISSION")
        result = client.post("/api/v1/telemetry", json=telemetry.model_dump(mode="json"))
        assert result.status_code == 201
        decision = result.json()["diagnostic_result"]
        assert decision["source"] == "engineering_rules"
        assert decision["fault_class"] == result.json()["predicted_fault"]
        assert decision["score_kind"] == "uncalibrated engineering score"
        history = client.get("/api/v1/engines/PIPELINE_TEST/history?limit=1")
        assert history.status_code == 200
        assert history.json()[0]["assessment"]["diagnostic_result"] == decision
        assert client.get("/api/v1/engines/PIPELINE_TEST/history?limit=0").status_code == 422
        assert client.post("/api/v1/telemetry", json={**telemetry.model_dump(mode="json"), "rpm": "NaN"}).status_code == 422
        stale = client.post("/api/v1/telemetry/synchronize", json=telemetry.model_copy(update={"timestamp": telemetry.timestamp - timedelta(seconds=1)}).model_dump(mode="json"))
        assert stale.status_code == 201
        assert stale.json()["assessment"]["diagnostic_result"]["source"] == "unavailable"


def test_runtime_model_checksum_rejects_corruption(tmp_path):
    path = tmp_path / "model.joblib"
    path.write_bytes(b"not a model")
    with pytest.raises(ModelCompatibilityError, match="checksum"):
        ArtifactMLProvider.load(path, TRUSTED_MODEL_SHA256)


def test_incompatible_model_score_dimensions_trigger_fallback():
    class BadEstimator(ControlledEstimator):
        def predict_proba(self, frame):
            import numpy as np
            return np.array([[1.0]])

    provider = ArtifactMLProvider(BadEstimator(), metadata())
    with pytest.raises(ValueError, match="shape"):
        provider.predict({"mission_phase": "cruise", **{name: BASE[name] for name in NUMERIC_FEATURES}})
