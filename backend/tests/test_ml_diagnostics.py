"""Software behavior tests using a controlled estimator, not aircraft validation."""
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import pytest

from backend.app.ml_diagnostics import ArtifactMLProvider, ModelCompatibilityError, load_provider
from backend.app.ml_features import FEATURES, NUMERIC_FEATURES, SCHEMA_VERSION
from backend.app.core import DigitalTwinCore
from backend.tests.test_diagnostics import BASE, sample


class ControlledEstimator:
    def __init__(self, fail=False):
        self.named_steps = {"classifier": SimpleNamespace(classes_=np.array(["Healthy", "Sensor_Drift"]))}
        self.fail = fail

    def predict_proba(self, frame):
        assert list(frame.columns) == FEATURES
        if self.fail:
            raise RuntimeError("controlled inference failure")
        return np.array([[.2, .8]])


class ClassEstimator:
    def __init__(self, labels, selected):
        self.named_steps = {"classifier": SimpleNamespace(classes_=np.array(labels))}
        self.selected = selected

    def predict_proba(self, frame):
        assert list(frame.columns) == FEATURES
        values = np.zeros(len(self.named_steps["classifier"].classes_))
        values[self.selected] = 1
        return np.array([values])


def metadata(**changes):
    return {"version": "controlled-v1", "feature_schema_version": SCHEMA_VERSION,
            "features": FEATURES, "classes": ["Healthy", "Sensor_Drift"],
            "release_gate_passed": False, "probability_status": "NOT_CALIBRATED", **changes}


def test_load_version_and_exact_feature_schema(tmp_path):
    path = tmp_path / "model.joblib"
    joblib.dump({"model": ControlledEstimator(), "metadata": metadata()}, path)
    loaded = ArtifactMLProvider.load(path)
    assert loaded.version == "controlled-v1"
    assert loaded.release_gate_passed is False
    with pytest.raises(ModelCompatibilityError):
        ArtifactMLProvider(ControlledEstimator(), metadata(features=list(reversed(FEATURES))))
    assert load_provider(str(tmp_path / "missing.joblib")) is None


def test_repository_candidate_loads_with_all_synthetic_classes():
    path = Path(__file__).resolve().parents[1] / "model_evaluation" / "outputs" / "live_candidate" / "model.joblib"
    provider = ArtifactMLProvider.load(path)
    assert provider.version == "live-telemetry-candidate-v1.0.0"
    assert len(provider.model.named_steps["classifier"].classes_) == 9
    assert provider.release_gate_passed is False
    prediction = provider.predict({"mission_phase": "cruise", **{name: BASE[name] for name in NUMERIC_FEATURES}})
    assert prediction["status"] == "available"
    assert prediction["fault_class"] in provider.model.named_steps["classifier"].classes_


def test_valid_feature_inference_and_missing_feature_rejection():
    provider = ArtifactMLProvider(ControlledEstimator(), metadata())
    features = {name: BASE[name] for name in NUMERIC_FEATURES}
    features["mission_phase"] = "cruise"
    outcome = provider.predict(features)
    assert outcome["fault_class"] == "Sensor_Drift"
    assert outcome["model_score"] == .8
    assert outcome["score_kind"] == "uncalibrated model score"
    with pytest.raises(ValueError):
        provider.predict({**features, "rpm": None})
    with pytest.raises(ValueError):
        provider.predict({**features, "mission_phase": "unknown"})


@pytest.mark.parametrize("label", ["Alternator_Degradation", "Bearing_Wear", "Combustion_Instability",
    "Cooling_System_Degradation", "Fuel_Injector_Degradation", "Healthy",
    "Lubrication_System_Degradation", "Sensor_Drift", "Spark_Plug_Misfire"])
def test_each_synthetic_class_mapping_is_preserved(label):
    labels = [label, "OTHER"]
    provider = ArtifactMLProvider(ClassEstimator(labels, 0), metadata(classes=labels))
    result = provider.predict({"mission_phase": "cruise", **{name: BASE[name] for name in NUMERIC_FEATURES}})
    assert result["fault_class"] == label


def test_ml_result_cache_is_bounded(monkeypatch):
    from backend.app import core as core_module
    monkeypatch.setattr(core_module, "settings", SimpleNamespace(ml_enabled=True, ml_artifact_path="controlled",
        environment="development", ml_allow_unvalidated=True))
    monkeypatch.setattr(core_module, "load_provider", lambda path: ArtifactMLProvider(ControlledEstimator(), metadata()))
    core = DigitalTwinCore()
    for index in range(140):
        core.synchronize(sample(engine_id=f"ENGINE_{index}"))
    assert len(core.diagnostics._ml_results) == 128


def test_ml_evidence_coexists_with_rules_and_failed_inference_falls_back(monkeypatch):
    from backend.app import core as core_module
    monkeypatch.setattr(core_module, "settings", SimpleNamespace(ml_enabled=True, ml_artifact_path="controlled", environment="development", ml_allow_unvalidated=True))
    monkeypatch.setattr(core_module, "load_provider", lambda path: ArtifactMLProvider(ControlledEstimator(), metadata()))
    core = DigitalTwinCore()
    assessment, state = core.synchronize(sample(oil_pressure_kpa=70, oil_temperature_c=145))
    assert state.faults.ml_inference["fault_class"] == "Sensor_Drift"
    assert assessment.ml_inference == state.faults.ml_inference
    assert assessment.predicted_fault == "Lubrication_System_Degradation"
    assert any(x.fault_code == "LUBRICATION_ISSUE" for x in state.faults.diagnostics)
    core.diagnostics.ml_provider = ArtifactMLProvider(ControlledEstimator(fail=True), metadata())
    later = sample(timestamp=BASE["timestamp"] + timedelta(seconds=5), oil_pressure_kpa=70, oil_temperature_c=145)
    assessment, state = core.synchronize(later)
    assert state.faults.ml_inference["status"] == "unavailable"
    assert assessment.predicted_fault == "Lubrication_System_Degradation"


def test_stale_telemetry_blocks_ml_without_reassuring_prediction(monkeypatch):
    from backend.app import core as core_module
    monkeypatch.setattr(core_module, "settings", SimpleNamespace(ml_enabled=True, ml_artifact_path="controlled", environment="development", ml_allow_unvalidated=True))
    monkeypatch.setattr(core_module, "load_provider", lambda path: ArtifactMLProvider(ControlledEstimator(), metadata()))
    core = DigitalTwinCore()
    core.synchronize(sample())
    assessment, state = core.synchronize(sample())
    assert not state.synchronized
    assert assessment.ml_inference["status"] == "blocked"


def test_unvalidated_artifact_is_not_served_without_explicit_development_override(monkeypatch):
    from backend.app import core as core_module
    monkeypatch.setattr(core_module, "settings", SimpleNamespace(ml_enabled=True, ml_artifact_path="controlled",
        environment="development", ml_allow_unvalidated=False))
    monkeypatch.setattr(core_module, "load_provider", lambda path: ArtifactMLProvider(ControlledEstimator(), metadata()))
    assessment, state = DigitalTwinCore().synchronize(sample())
    assert assessment.ml_inference["status"] == "unavailable"
    assert state.faults.ml_inference["status"] == "unavailable"
