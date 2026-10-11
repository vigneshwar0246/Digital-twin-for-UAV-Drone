"""Optional, version-checked inference for the synthetic live-compatible candidate."""
from functools import lru_cache
import hashlib
import json
import logging
import math
from pathlib import Path

from .ml_features import FEATURES, NUMERIC_FEATURES, SCHEMA_VERSION

logger = logging.getLogger(__name__)
TRUSTED_MODEL_PATH = Path(__file__).resolve().parents[1] / "model_evaluation" / "outputs" / "live_candidate" / "model.joblib"
TRUSTED_MODEL_SHA256 = "e8c637760bb2a4154af4042258e1bbc7956056514cd5ef9100829cf3787049b3"


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
    def load(cls, path: Path, expected_sha256: str | None = None):
        import joblib
        import sklearn
        if expected_sha256 is not None:
            with path.open("rb") as handle:
                actual = hashlib.file_digest(handle, "sha256").hexdigest()
            if actual != expected_sha256:
                raise ModelCompatibilityError("model artifact checksum does not match trusted record")
        sidecar = path.with_name("evaluation.json")
        if expected_sha256 is not None and not sidecar.is_file():
            raise ModelCompatibilityError("trusted model evaluation record is missing")
        if sidecar.exists():
            report = json.loads(sidecar.read_text(encoding="utf-8"))
            declared = report.get("sklearn_version")
            if declared is not None and declared != sklearn.__version__:
                raise ModelCompatibilityError("model scikit-learn version does not match runtime")
        artifact = joblib.load(path)
        if not isinstance(artifact, dict) or "model" not in artifact or "metadata" not in artifact:
            raise ModelCompatibilityError("invalid model artifact")
        if sidecar.exists():
            for key in ("version", "feature_schema_version", "dataset_sha256", "release_gate_passed", "probability_status"):
                if report.get(key) != artifact["metadata"].get(key):
                    raise ModelCompatibilityError(f"model metadata differs from evaluation record: {key}")
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
        matrix = self.model.predict_proba(frame)
        if getattr(matrix, "shape", None) != (1, len(self.model.named_steps["classifier"].classes_)):
            raise ValueError("model returned an incompatible class-score shape")
        scores = matrix[0]
        if not all(math.isfinite(float(value)) and 0 <= float(value) <= 1 for value in scores) or abs(float(sum(scores))-1) > .01:
            raise ValueError("model returned invalid class scores")
        index = int(scores.argmax())
        return {"status": "available", "fault_class": str(self.model.named_steps["classifier"].classes_[index]),
                "model_score": round(float(scores[index]), 4), "score_kind": "uncalibrated model score",
                "model_version": self.version, "release_gate_passed": self.release_gate_passed}


@lru_cache(maxsize=2)
def load_provider(path: str):
    try:
        target = Path(path).resolve()
        if target != TRUSTED_MODEL_PATH.resolve():
            raise ModelCompatibilityError("runtime model path is not a trusted repository artifact")
        return ArtifactMLProvider.load(target, TRUSTED_MODEL_SHA256)
    except Exception as exc:
        logger.warning("ML model unavailable: %s", exc)
        return None
