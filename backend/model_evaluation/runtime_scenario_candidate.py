"""Train an isolated classifier for the application's synthetic scenarios.

This benchmark measures only the runtime simulator. It cannot validate a real
engine or replace the historical nine-fault release audit. Output paths must be
new so historical datasets and model artifacts cannot be overwritten.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time

import joblib
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.utils.class_weight import compute_sample_weight

from backend.app.schemas import DegradationScenario, MissionProfile, SimulationRequest
from backend.app.simulation import build_mission
from backend.app.ml_features import SCENARIO_FEATURES
from .experimental_live_features import TelemetryState
from .controlled_live_experiments import matrix
from .scenario_causal_features import (
    FEATURES_V2, FEATURES_V3, CombustionTelemetryState, ScenarioTelemetryState,
    matrix as scenario_matrix, matrix_with_combustion,
)

SEED = 26054
PROFILES = tuple(MissionProfile)
SCENARIOS = tuple(DegradationScenario)
FEATURE_COLUMNS = SCENARIO_FEATURES
PARTITIONS = {
    "fit": (1101, 1102, 1103, 1104),
    "validation": (2201, 2202),
    "challenge": (3301, 3302),
}
SEVERITY_PARTITIONS = {
    "fit": PARTITIONS["fit"],
    "validation": PARTITIONS["validation"],
    "challenge": (5501, 5502),
}
SENSOR_PARTITIONS = {
    "fit": PARTITIONS["fit"],
    "validation": PARTITIONS["validation"],
    "challenge": (6601, 6602),
}
COMBUSTION_PARTITIONS = {
    "fit": PARTITIONS["fit"],
    "validation": PARTITIONS["validation"],
    "challenge": (7701, 7702),
}
PROTOCOLS = {
    "runtime-v1": (PARTITIONS, (.8,), FEATURE_COLUMNS, matrix, TelemetryState),
    "severity-v2": (SEVERITY_PARTITIONS, (.2, .5, .8), FEATURE_COLUMNS, matrix, TelemetryState),
    "severity-v3": (SENSOR_PARTITIONS, (.2, .5, .8), FEATURES_V2, scenario_matrix, ScenarioTelemetryState),
    "severity-v4": (COMBUSTION_PARTITIONS, (.2, .5, .8), FEATURES_V3,
                    matrix_with_combustion, CombustionTelemetryState),
}
MIN_FAULT_RECALL = .80


def mission_frame(seed: int, profile: MissionProfile, scenario: DegradationScenario,
                  severity: float = .8) -> pd.DataFrame:
    """One deterministic mission; labels come from scenario truth, never sensors."""
    start = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=seed)
    request = SimulationRequest(
        profile=profile, degradation_scenario=scenario, seed=seed,
        duration_minutes=10, interval_seconds=5,
        engine_id=f"SYNTHETIC_SEED_{seed}",
        mission_id=f"SYN_{seed}_{profile.value}_{scenario.value}_{int(severity * 100):02d}",
        start_time=start,
        degradation_severity=severity,
    )
    mission = build_mission(request)
    rows = []
    for telemetry, truth in zip(mission.telemetry, mission.scenario_truth, strict=True):
        row = telemetry.model_dump()
        row["time_seconds"] = truth.time_seconds
        row["severity_level"] = severity
        row["fault_type"] = scenario.value if truth.fault_active else DegradationScenario.NONE.value
        rows.append(row)
    return pd.DataFrame(rows)


def make_partition(seeds: tuple[int, ...], severities: tuple[float, ...],
                   features: list[str], feature_matrix) -> pd.DataFrame:
    frames = [mission_frame(seed, profile, scenario, severity)
              for seed in seeds for severity in severities
              for profile in PROFILES for scenario in SCENARIOS]
    return feature_matrix(pd.concat(frames, ignore_index=True), features)


def score(model: Pipeline, frame: pd.DataFrame, features: list[str] = FEATURE_COLUMNS) -> dict:
    labels = list(model.named_steps["classifier"].classes_)
    predictions = model.predict(frame[features])
    report = classification_report(frame.fault_type, predictions, labels=labels,
                                   output_dict=True, zero_division=0)
    return {
        "samples": len(frame),
        "accuracy": float(accuracy_score(frame.fault_type, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(frame.fault_type, predictions)),
        "macro_f1": float(report["macro avg"]["f1-score"]),
        "per_class": {label: {k: float(report[label][k]) for k in
                                ("precision", "recall", "f1-score", "support")}
                      for label in labels},
        "labels": labels,
        "confusion_matrix": confusion_matrix(frame.fault_type, predictions, labels=labels).tolist(),
    }


def candidate(estimator, features: list[str]) -> Pipeline:
    transform = ColumnTransformer([
        ("phase", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["mission_phase"]),
        ("numeric", "passthrough", [c for c in features if c != "mission_phase"]),
    ])
    return Pipeline([("features", transform), ("classifier", estimator)])


def run(output: Path, protocol: str = "runtime-v1") -> dict:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"output already exists: {output}")
    if protocol not in PROTOCOLS:
        raise ValueError(f"unknown evaluation protocol: {protocol}")
    partitions, severities, features, feature_matrix, feature_state = PROTOCOLS[protocol]
    excluded = {"mission_id", "engine_id", "fault_type", "scenario_truth", "severity_level",
                "degradation_scenario", "seed", "timestamp", "time_seconds"}
    if excluded.intersection(features):
        raise ValueError("a prohibited identity, truth, or time column entered the model features")
    all_seeds = [seed for group in partitions.values() for seed in group]
    if len(all_seeds) != len(set(all_seeds)):
        raise ValueError("training and holdout seeds must be disjoint")
    data = {name: make_partition(seeds, severities, features, feature_matrix)
            for name, seeds in partitions.items()}
    expected_labels = {scenario.value for scenario in SCENARIOS}
    if any(set(frame.fault_type) != expected_labels for frame in data.values()):
        raise ValueError("every partition must cover every synthetic scenario")
    fit = data["fit"]
    assert set(fit.mission_id).isdisjoint(data["validation"].mission_id)
    assert set(fit.mission_id).isdisjoint(data["challenge"].mission_id)
    assert set(data["validation"].mission_id).isdisjoint(data["challenge"].mission_id)
    assert set(fit.engine_id).isdisjoint(data["validation"].engine_id)
    assert set(fit.engine_id).isdisjoint(data["challenge"].engine_id)
    weights = compute_sample_weight(class_weight="balanced", y=fit.fault_type)
    trials = {
        "hgb": HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=31,
                                                learning_rate=.08, random_state=SEED),
        "extra_trees": ExtraTreesClassifier(n_estimators=120, min_samples_leaf=2,
                                             max_features=.8, n_jobs=-1, random_state=SEED),
    }
    validation = {}
    selected = None
    for name, estimator in trials.items():
        model = candidate(estimator, features)
        start = time.perf_counter()
        model.fit(fit[features], fit.fault_type, classifier__sample_weight=weights)
        result = score(model, data["validation"], features)
        validation[name] = {"training_seconds": time.perf_counter() - start,
                            "metrics": result, "parameters": estimator.get_params()}
        rank = (result["macro_f1"], result["balanced_accuracy"])
        if selected is None or rank > selected[0]:
            selected = (rank, name, model)
        print(name, "validation macro_f1", round(result["macro_f1"], 4), flush=True)
    assert selected is not None
    _, name, model = selected
    assessments = {part: score(model, data[part], features) for part in ("validation", "challenge")}
    by_severity = {part: {str(severity): score(model, data[part][data[part].severity_level.eq(severity)], features)
                          for severity in severities} for part in assessments}
    required = {part: all(metrics["per_class"][label.value]["recall"] >= MIN_FAULT_RECALL
                          for metrics in by_severity[part].values()
                          for label in SCENARIOS if label is not DegradationScenario.NONE)
                for part in assessments}
    report = {
        "purpose": "synthetic runtime-scenario benchmark only",
        "real_engine_validation": False,
        "historical_fault_model_promoted": False,
        "generator_version": "mission-simulator-v2",
        "protocol": protocol,
        "severity_levels": list(severities),
        "seed": SEED,
        "profile_values": [x.value for x in PROFILES],
        "scenario_values": [x.value for x in SCENARIOS],
        "split_seed_groups": {k: list(v) for k, v in partitions.items()},
        "partition_rows": {k: len(v) for k, v in data.items()},
        "partition_missions": {k: int(v.mission_id.nunique()) for k, v in data.items()},
        "split_limitation": "The simulator does not model engine identity; held-out IDs are independent random seeds, not physical engine generalization.",
        "features": features,
        "temporal_policy": "current and earlier samples only, reset per mission",
        "selection_policy": "validation macro F1 then balanced accuracy; challenge used once after selection",
        "minimum_fault_recall": MIN_FAULT_RECALL,
        "required_split_pass": required,
        "synthetic_gate_passed": bool(all(required.values())),
        "selected": name,
        "validation_trials": validation,
        "selected_assessments": assessments,
        "per_severity_assessments": by_severity,
        "sklearn_version": sklearn.__version__,
        "simulator_sha256": hashlib.sha256(Path(build_mission.__code__.co_filename).read_bytes()).hexdigest(),
        "offline_features_sha256": hashlib.sha256(Path(feature_matrix.__code__.co_filename).read_bytes()).hexdigest(),
        "streaming_features_sha256": hashlib.sha256(Path(feature_state.__init__.__code__.co_filename).read_bytes()).hexdigest(),
    }
    output.mkdir(parents=True)
    artifact_path = output / "research_model.joblib"
    joblib.dump({"model": model, "features": features,
                 "purpose": report["purpose"], "synthetic_gate_passed": report["synthetic_gate_passed"]},
                artifact_path)
    with artifact_path.open("rb") as artifact_file:
        report["artifact_sha256"] = hashlib.file_digest(artifact_file, "sha256").hexdigest()
    (output / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"selected": name, "synthetic_gate_passed": report["synthetic_gate_passed"],
                      "metrics": {part: {k: assessments[part][k] for k in
                                         ("accuracy", "balanced_accuracy", "macro_f1")}
                                  for part in assessments}}, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="new output directory; existing paths are refused")
    parser.add_argument("--protocol", choices=tuple(PROTOCOLS), default="runtime-v1")
    args = parser.parse_args()
    run(args.output, args.protocol)
