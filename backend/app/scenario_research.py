"""Trusted, opt-in inference for saved synthetic simulator missions only."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from math import isfinite
from pydantic import ValidationError

from .schemas import Telemetry

from .ml_features import SCENARIO_FEATURES

TRUSTED_SCENARIO_MODEL_PATH = (
    Path(__file__).resolve().parents[1] / "runtime" / "scenario_model" / "research_model.joblib"
)


class ScenarioModelError(ValueError):
    pass


@lru_cache(maxsize=1)
def load_scenario_provider():
    """Verify the fixed local artifact and sidecar before deserialization."""
    import joblib
    import sklearn

    path = TRUSTED_SCENARIO_MODEL_PATH
    sidecar = path.with_name("evaluation.json")
    if not path.is_file() or not sidecar.is_file():
        raise ScenarioModelError("synthetic scenario model or evaluation record is missing")
    try:
        report = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ScenarioModelError("synthetic scenario evaluation record is invalid") from exc
    if report.get("purpose") != "synthetic runtime-scenario benchmark only":
        raise ScenarioModelError("synthetic scenario model purpose is incompatible")
    if report.get("sklearn_version") != sklearn.__version__:
        raise ScenarioModelError("synthetic scenario model scikit-learn version differs")
    from backend.model_evaluation.controlled_live_experiments import matrix
    from backend.model_evaluation.experimental_live_features import TelemetryState
    from backend.model_evaluation.scenario_causal_features import (
        FEATURES_V2, FEATURES_V3, CombustionTelemetryState, ScenarioTelemetryState,
        matrix as scenario_matrix, matrix_with_combustion,
    )
    features = report.get("features")
    if features == SCENARIO_FEATURES:
        feature_matrix, feature_state = matrix, TelemetryState
    elif features == FEATURES_V2 and report.get("protocol") == "severity-v3":
        feature_matrix, feature_state = scenario_matrix, ScenarioTelemetryState
    elif features == FEATURES_V3 and report.get("protocol") == "severity-v4":
        feature_matrix, feature_state = matrix_with_combustion, CombustionTelemetryState
    else:
        raise ScenarioModelError("synthetic scenario feature schema differs")
    from .simulation import GENERATOR_VERSION, build_mission
    if report.get("generator_version") != GENERATOR_VERSION:
        raise ScenarioModelError("synthetic scenario generator version differs")
    simulator_hash = hashlib.sha256(Path(build_mission.__code__.co_filename).read_bytes()).hexdigest()
    if report.get("simulator_sha256") != simulator_hash:
        raise ScenarioModelError("synthetic scenario generator source differs")
    offline_hash = hashlib.sha256(Path(feature_matrix.__code__.co_filename).read_bytes()).hexdigest()
    streaming_hash = hashlib.sha256(Path(feature_state.__init__.__code__.co_filename).read_bytes()).hexdigest()
    if (report.get("offline_features_sha256") != offline_hash
            or report.get("streaming_features_sha256") != streaming_hash):
        raise ScenarioModelError("synthetic scenario feature implementation differs")
    if report.get("synthetic_gate_passed") is not True:
        raise ScenarioModelError("synthetic scenario model failed its evaluation gate")
    expected = report.get("artifact_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ScenarioModelError("synthetic scenario model checksum is unavailable")
    with path.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
            raise ScenarioModelError("synthetic scenario model checksum differs")
    artifact = joblib.load(path)
    if not isinstance(artifact, dict) or artifact.get("features") != features:
        raise ScenarioModelError("synthetic scenario model feature contract differs")
    if artifact.get("synthetic_gate_passed") is not True or artifact.get("purpose") != report["purpose"]:
        raise ScenarioModelError("synthetic scenario model metadata differs")
    model = artifact.get("model")
    classes = getattr(getattr(model, "named_steps", {}).get("classifier"), "classes_", None)
    if classes is None or list(classes) != sorted(report.get("scenario_values", [])):
        raise ScenarioModelError("synthetic scenario class mapping differs")
    return model, report


def predict_saved_synthetic_mission(snapshot: dict) -> dict:
    """Use saved telemetry only; scenario truth is never an inference feature."""
    import numpy as np
    import pandas as pd

    from backend.model_evaluation.experimental_live_features import TelemetryState
    from backend.model_evaluation.scenario_causal_features import (
        FEATURES_V2, FEATURES_V3, CombustionTelemetryState, ScenarioTelemetryState,
    )

    if snapshot.get("duration_seconds") != 600 or snapshot.get("interval_seconds") != 5:
        raise ScenarioModelError("synthetic scenario model requires a ten-minute mission sampled every five seconds")
    model, report = load_scenario_provider()
    samples = snapshot.get("telemetry")
    if not isinstance(samples, list) or not samples:
        raise ScenarioModelError("saved simulation telemetry is unavailable")
    mission_id = snapshot.get("mission_id")
    if not isinstance(mission_id, str) or not mission_id:
        raise ScenarioModelError("saved simulation mission ID is unavailable")
    if snapshot.get("generator_version") != report["generator_version"]:
        raise ScenarioModelError("saved simulation generator version differs")
    try:
        input_sha256 = hashlib.sha256(json.dumps(samples, sort_keys=True, allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError) as exc:
        raise ScenarioModelError("saved simulation telemetry is malformed") from exc
    feature_columns = report["features"]
    state = (CombustionTelemetryState() if feature_columns == FEATURES_V3
             else ScenarioTelemetryState() if feature_columns == FEATURES_V2
             else TelemetryState())
    try:
        origin = datetime.fromisoformat(samples[0]["timestamp"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ScenarioModelError("saved simulation timestamps are invalid") from exc
    if len(samples) != 120:
        raise ScenarioModelError("saved simulation sample count differs from the evaluated domain")
    rows = []
    times = []
    for sample in samples:
        if not isinstance(sample, dict):
            raise ScenarioModelError("saved simulation telemetry is malformed")
        if sample.get("mission_id") != mission_id:
            raise ScenarioModelError("saved simulation contains another mission")
        try:
            validated = Telemetry.model_validate(sample)
            timestamp = validated.timestamp
            seconds = (timestamp - origin).total_seconds()
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise ScenarioModelError("saved simulation telemetry or timestamps are invalid") from exc
        if not isfinite(seconds) or abs(seconds - len(times) * 5) > 1e-6:
            raise ScenarioModelError("saved simulation timestamps differ from five-second sampling")
        try:
            rows.append(state.push(mission_id, seconds, sample))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ScenarioModelError(f"saved simulation telemetry cannot be scored: {exc}") from exc
        times.append(seconds)
    if any(set(feature_columns) - set(row) for row in rows):
        raise ScenarioModelError("synthetic scenario feature schema differs")
    frame = pd.DataFrame(rows, columns=feature_columns)
    if not np.isfinite(frame.drop(columns=["mission_phase"]).to_numpy(dtype=float)).all():
        raise ScenarioModelError("synthetic scenario features contain non-finite values")
    try:
        predictions = model.predict(frame)
        scores = model.predict_proba(frame)
    except Exception as exc:
        raise ScenarioModelError("synthetic scenario prediction failed") from exc
    labels = list(model.named_steps["classifier"].classes_)
    if (len(predictions) != len(samples) or scores.shape != (len(samples), len(labels)) or not np.isfinite(scores).all()
            or (scores < 0).any() or (scores > 1).any()
            or not np.allclose(scores.sum(axis=1), 1, atol=.01)):
        raise ScenarioModelError("synthetic scenario model returned invalid scores")
    output = []
    for sample, seconds, label, probability in zip(samples, times, predictions, scores, strict=True):
        if label not in labels:
            raise ScenarioModelError("synthetic scenario model returned an unknown class")
        index = labels.index(label)
        output.append({"timestamp": sample["timestamp"], "time_seconds": seconds,
                       "scenario_class": str(label), "model_score": round(float(probability[index]), 4),
                       "score_type": "uncalibrated_classifier_score"})
    return {
        "mission_id": mission_id,
        "source": "synthetic_scenario_ml_research",
        "model_selected": report["selected"],
        "model_version": report["protocol"],
        "model_sha256": report["artifact_sha256"],
        "input_sha256": input_sha256,
        "feature_schema": feature_columns,
        "validation_status": "synthetic_gate_passed; real_engine_not_validated",
        "model_score_kind": "uncalibrated model score, not a failure probability",
        "synthetic_validation_accuracy": report["selected_assessments"]["validation"]["accuracy"],
        "synthetic_challenge_accuracy": report["selected_assessments"]["challenge"]["accuracy"],
        "synthetic_gate_passed": True,
        "real_engine_validation": False,
        "warning": "Generated-simulator pattern recognition only; not an aircraft diagnosis.",
        "class_counts": dict(Counter(item["scenario_class"] for item in output)),
        "predictions": output,
    }
