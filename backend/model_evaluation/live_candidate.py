"""Bounded, leakage-safe search for a live-telemetry-compatible classifier.

Selection uses only the engine-disjoint validation partition. The challenge and
time-forward partitions are evaluated once after selection, never for tuning.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import time

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.utils.class_weight import compute_sample_weight

from backend.app.ml_features import FEATURES, NUMERIC_FEATURES, SCHEMA_VERSION
from .evaluate_fault_classifier import DATA_DIR, EXCLUDED, IMPORTANT_FAULTS, MIN_RECALL, OUTPUT_DIR, TARGET
from .evaluation_protocol import build_evaluation_splits

SEED = 26054
VERSION = "live-telemetry-candidate-v1.0.0"
NUMERIC = NUMERIC_FEATURES


def report(model, frame):
    start = time.perf_counter()
    predictions = model.predict(frame[FEATURES])
    latency = (time.perf_counter() - start) / len(frame) * 1000
    labels = list(model.named_steps["classifier"].classes_)
    classes = classification_report(frame[TARGET], predictions, labels=labels, output_dict=True, zero_division=0)
    per_class = {name: {key: float(classes[name][key]) for key in ("precision", "recall", "f1-score", "support")}
                 for name in labels}
    return {
        "samples": len(frame), "accuracy": accuracy_score(frame[TARGET], predictions),
        "balanced_accuracy": balanced_accuracy_score(frame[TARGET], predictions),
        "macro_precision": classes["macro avg"]["precision"],
        "macro_recall": classes["macro avg"]["recall"],
        "macro_f1": classes["macro avg"]["f1-score"],
        "weighted_f1": classes["weighted avg"]["f1-score"],
        "inference_ms_per_sample": latency, "per_class": per_class,
        "confusion_matrix": confusion_matrix(frame[TARGET], predictions, labels=labels).tolist(),
        "labels": labels,
    }


def run():
    full_path = DATA_DIR / "aero_engine_full.csv"
    full = pd.read_csv(full_path, keep_default_na=False)
    assert not set(FEATURES) & EXCLUDED
    assert set(FEATURES) <= set(full)
    splits = build_evaluation_splits(full, TARGET, SEED)
    weighting = compute_sample_weight(class_weight="balanced", y=splits.fit[TARGET])
    weighting *= splits.fit[TARGET].map({"Cooling_System_Degradation": 5.0, "Sensor_Drift": 1.6}).fillna(1).to_numpy()
    candidates = {
        "hgb_live": HistGradientBoostingClassifier(max_iter=220, learning_rate=.075, max_leaf_nodes=31,
                                                      l2_regularization=.5, random_state=SEED),
        "hgb_regularized": HistGradientBoostingClassifier(max_iter=300, learning_rate=.045, max_leaf_nodes=15,
                                                             min_samples_leaf=30, l2_regularization=2.0, random_state=SEED),
        "extra_trees": ExtraTreesClassifier(n_estimators=160, min_samples_leaf=3, max_features=.8,
                                              n_jobs=-1, random_state=SEED),
    }
    trials = {}
    selected = None
    for name, estimator in candidates.items():
        processor = ColumnTransformer([
            ("phase", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["mission_phase"]),
            ("numeric", "passthrough", NUMERIC),
        ])
        model = Pipeline([("features", processor), ("classifier", estimator)])
        start = time.perf_counter()
        model.fit(splits.fit[FEATURES], splits.fit[TARGET], classifier__sample_weight=weighting)
        training_seconds = time.perf_counter() - start
        validation = report(model, splits.validation)
        trials[name] = {"parameters": estimator.get_params(), "training_seconds": training_seconds,
                        "validation": validation}
        rank = (validation["macro_f1"], validation["balanced_accuracy"])
        if selected is None or rank > selected[0]:
            selected = (rank, name, model)
    assert selected is not None
    _, name, model = selected
    assessments = {part: report(model, getattr(splits, part)) for part in ("time_forward", "validation", "challenge")}
    required = {part: all(assessments[part]["per_class"][label]["support"] > 0 and
                          assessments[part]["per_class"][label]["recall"] >= MIN_RECALL
                          for label in IMPORTANT_FAULTS) for part in assessments}
    gate = bool(all(required.values()) and all(splits.manifest["engine_disjoint"].values()) and splits.manifest["mission_disjoint"])
    metadata = {
        "version": VERSION, "selected": name, "feature_schema_version": SCHEMA_VERSION,
        "sklearn_version": sklearn.__version__,
        "features": FEATURES, "numeric_features": NUMERIC, "classes": list(model.named_steps["classifier"].classes_),
        "dataset_sha256": hashlib.sha256(full_path.read_bytes()).hexdigest(),
        "split_manifest": splits.manifest, "seed": SEED, "minimum_important_fault_recall": MIN_RECALL,
        "required_split_pass": required, "release_gate_passed": gate,
        "status": "VALIDATED_CANDIDATE" if gate else "NOT_VALIDATED",
        "probability_status": "NOT_CALIBRATED", "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "selection_policy": "highest validation macro F1, then balanced accuracy",
        "training_weighting": "balanced inverse frequency; cooling x5; sensor drift x1.6",
        "candidates": trials, "selected_assessments": assessments,
    }
    destination = OUTPUT_DIR / "live_candidate"
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "evaluation.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    joblib.dump({"model": model, "metadata": {key: metadata[key] for key in
                ("version", "feature_schema_version", "sklearn_version", "features", "classes", "dataset_sha256",
                 "release_gate_passed", "status", "probability_status")}}, destination / "model.joblib")
    print(json.dumps({"selected": name, "gate_passed": gate,
                      "metrics": {part: {key: assessments[part][key] for key in
                                  ("accuracy", "balanced_accuracy", "macro_f1")} for part in assessments}}, indent=2))
    return metadata


if __name__ == "__main__":
    run()
