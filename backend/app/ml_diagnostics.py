"""Optional, version-checked inference for the synthetic live-compatible candidate."""
from functools import lru_cache
import logging
import math
from pathlib import Path

from .ml_features import FEATURES, NUMERIC_FEATURES, SCHEMA_VERSION

logger = logging.getLogger(__name__)


class ModelCompatibilityError(ValueError):
    pass


class ArtifactMLProvider:
    calibrated = False

    def __init__(self, model, metadata: dict):
        import sklearn
        if metadata.get("sklearn_version") not in (None, sklearn.__version__):
            raise ModelCompatibilityError("model scikit-learn version does not match runtime")
        if metadata.get("feature_schema_version") != SCHEMA_VERSION or metadata.get("features") != FEATURES:
            raise ModelCompatibilityError("model feature schema does not match live telemetry")
        classes = metadata.get("classes")
        if not isinstance(classes, list) or not classes or list(model.named_steps["classifier"].classes_) != classes:
            raise ModelCompatibilityError("model class mapping is incompatible")
        if metadata.get("probability_status") != "NOT_CALIBRATED":
            raise ModelCompatibilityError("unexpected calibration declaration")
        self.model = model
        self.version = str(metadata["version"])
        self.release_gate_passed = metadata.get("release_gate_passed") is True

    @classmethod
    def load(cls, path: Path):
        import joblib
        import json
        import sklearn
        sidecar = path.with_name("evaluation.json")
        if sidecar.exists():
            declared = json.loads(sidecar.read_text(encoding="utf-8")).get("sklearn_version")
            if declared is not None and declared != sklearn.__version__:
                raise ModelCompatibilityError("model scikit-learn version does not match runtime")
        artifact = joblib.load(path)
        if not isinstance(artifact, dict) or "model" not in artifact or "metadata" not in artifact:
            raise ModelCompatibilityError("invalid model artifact")
        return cls(artifact["model"], artifact["metadata"])

    def predict(self, features: dict):
        import pandas as pd
        phase = features.get("mission_phase")
        if not isinstance(phase, str) or not phase.strip() or phase.lower() == "unknown":
            raise ValueError("mission phase is unavailable")
        for name in NUMERIC_FEATURES:
            value = features.get(name)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"invalid or missing feature: {name}")
        frame = pd.DataFrame([{name: features[name] for name in FEATURES}], columns=FEATURES)
        scores = self.model.predict_proba(frame)[0]
        if not all(math.isfinite(float(value)) and 0 <= float(value) <= 1 for value in scores) or abs(float(sum(scores))-1) > .01:
            raise ValueError("model returned invalid class scores")
        index = int(scores.argmax())
        return {"status": "available", "fault_class": str(self.model.named_steps["classifier"].classes_[index]),
                "model_score": round(float(scores[index]), 4), "score_kind": "uncalibrated model score",
                "model_version": self.version, "release_gate_passed": self.release_gate_passed}


@lru_cache(maxsize=2)
def load_provider(path: str):
    try:
        return ArtifactMLProvider.load(Path(path))
    except Exception as exc:
        logger.warning("ML model unavailable: %s", exc)
        return None
