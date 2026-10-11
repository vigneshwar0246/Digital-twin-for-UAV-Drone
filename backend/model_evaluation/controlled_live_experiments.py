"""Reproducible, validation-only live-feature ablations and frozen final audit.

Run from repository root with the baseline scikit-learn 1.7.2 environment:
    python -B -m backend.model_evaluation.controlled_live_experiments select
    python -B -m backend.model_evaluation.controlled_live_experiments audit
The audit command requires the saved selection and refuses a second audit.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from backend.app.ml_features import FEATURES, NUMERIC_FEATURES
from .evaluate_fault_classifier import DATA_DIR, IMPORTANT_FAULTS, MIN_RECALL
from .evaluation_protocol import build_evaluation_splits

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs" / "controlled_live"
SEED = 26054
DATA_HASH = "2b9a25ab4600bebb4d3d1d95504e22889ce86714bb680b7e68d524d3cb68041e"
CURRENT = ["cht_spread_c", "egt_spread_c", "cht_mean_c", "egt_mean_c",
           "cht_upper_pair_spread_c", "cht_lower_pair_spread_c"]
TEMPORAL = ([f"{x}_{suffix}" for x in ("rpm", "air_fuel_ratio", "vibration_rms", "cht_mean_c", "egt_mean_c")
             for suffix in ("delta", "rolling_std_7", "rolling_std_21")]
            + [f"{x}_rolling_mean_21" for x in ("cht_spread_c", "egt_spread_c")]
            + ["cht_rise_rate_c_per_s"])
# Air/fuel ratio is absent from the current live contract. Never use its history.
TEMPORAL = [x for x in TEMPORAL if not x.startswith("air_fuel_ratio_")]
COOLING_CURRENT = ["cht_load_residual_c", "cht_egt_gap_c", "cht_peak_over_median_c"]
COOLING_TEMPORAL = ["cht_load_residual_c_rolling_mean_21", "cht_load_residual_c_delta",
                    "oil_temperature_c_rolling_mean_21", "oil_temperature_c_delta"]


def load():
    path = DATA_DIR / "aero_engine_full.csv"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == DATA_HASH
    assert sklearn.__version__ == "1.7.2", "Use the reproduced committed baseline environment"
    splits = build_evaluation_splits(pd.read_csv(path, keep_default_na=False), "fault_type", SEED)
    committed = json.loads((HERE / "outputs/reports/split_manifest.json").read_text())
    assert splits.manifest == committed, "Split manifest drift"
    assert MIN_RECALL == .80
    return splits


def matrix(frame, features):
    derived = frame.sort_values(["mission_id", "time_seconds"]).copy()
    cht = [f"cylinder_head_temp_{i}_c" for i in range(1, 5)]
    egt = [f"exhaust_gas_temp_{i}_c" for i in range(1, 5)]
    derived["cht_spread_c"] = derived[cht].max(axis=1) - derived[cht].min(axis=1)
    derived["egt_spread_c"] = derived[egt].max(axis=1) - derived[egt].min(axis=1)
    derived["cht_mean_c"] = derived[cht].mean(axis=1)
    derived["egt_mean_c"] = derived[egt].mean(axis=1)
    ordered = np.sort(derived[cht].to_numpy(), axis=1)
    derived["cht_upper_pair_spread_c"] = ordered[:, 3] - ordered[:, 1]
    derived["cht_lower_pair_spread_c"] = ordered[:, 2] - ordered[:, 0]
    derived["cht_load_residual_c"] = (derived["cht_mean_c"] - derived.ambient_temperature_c
        - 1.25 * derived.engine_load_percent - .0014 * derived.altitude_m)
    derived["cht_egt_gap_c"] = derived["cht_mean_c"] - derived["egt_mean_c"]
    derived["cht_peak_over_median_c"] = ordered[:, 3] - np.median(ordered, axis=1)
    grouped = derived.groupby("mission_id", sort=False)
    for col in ("rpm", "vibration_rms", "cht_mean_c", "egt_mean_c"):
        derived[f"{col}_delta"] = grouped[col].diff().fillna(0)
        for window in (7, 21):
            derived[f"{col}_rolling_std_{window}"] = (grouped[col].rolling(window, min_periods=2)
                .std().reset_index(level=0, drop=True).fillna(0))
    for col in ("cht_spread_c", "egt_spread_c"):
        derived[f"{col}_rolling_mean_21"] = (grouped[col].rolling(21, min_periods=1)
            .mean().reset_index(level=0, drop=True))
    dt = grouped.time_seconds.diff().replace(0, np.nan).fillna(1)
    derived["cht_rise_rate_c_per_s"] = derived["cht_mean_c_delta"] / dt
    for col in ("cht_load_residual_c", "oil_temperature_c"):
        derived[f"{col}_delta"] = grouped[col].diff().fillna(0)
        derived[f"{col}_rolling_mean_21"] = (grouped[col].rolling(21, min_periods=1)
            .mean().reset_index(level=0, drop=True))
    missing = set(features) - set(derived)
    assert not missing, missing
    return derived


def config(name):
    base = dict(max_iter=220, learning_rate=.075, max_leaf_nodes=31,
                l2_regularization=.5, random_state=SEED)
    if name == "hgb_baseline":
        return HistGradientBoostingClassifier(**base)
    if name == "hgb_regularized":
        return HistGradientBoostingClassifier(max_iter=300, learning_rate=.045,
               max_leaf_nodes=15, min_samples_leaf=30, l2_regularization=2., random_state=SEED)
    if name == "hgb_shallow":
        return HistGradientBoostingClassifier(max_iter=220, learning_rate=.075,
               max_leaf_nodes=15, min_samples_leaf=20, l2_regularization=.5, random_state=SEED)
    if name == "extra_trees":
        return ExtraTreesClassifier(n_estimators=160, min_samples_leaf=3,
                                    max_features=.8, n_jobs=1, random_state=SEED)
    raise ValueError(name)


def build(features, scaling, estimator):
    numeric = [x for x in features if x != "mission_phase"]
    prep = ColumnTransformer([
        ("numeric", StandardScaler() if scaling else "passthrough", numeric),
        ("phase", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["mission_phase"]),
    ])
    return Pipeline([("features", prep), ("classifier", config(estimator))])


def assess(model, frame, features):
    labels = list(model.named_steps["classifier"].classes_)
    pred = model.predict(frame[features])
    report = classification_report(frame.fault_type, pred, labels=labels,
                                   output_dict=True, zero_division=0)
    return {"samples": len(frame), "accuracy": accuracy_score(frame.fault_type, pred),
            "balanced_accuracy": balanced_accuracy_score(frame.fault_type, pred),
            "macro_f1": report["macro avg"]["f1-score"],
            "per_class": {x: {k: report[x][k] for k in ("precision", "recall", "f1-score", "support")}
                          for x in labels},
            "confusion_matrix": confusion_matrix(frame.fault_type, pred, labels=labels).tolist(),
            "labels": labels,
            "false_positives": {x: int(sum(pred == x) - sum((pred == x) & (frame.fault_type.to_numpy() == x)))
                                for x in labels},
            "recall_gate": all(report[x]["support"] > 0 and report[x]["recall"] >= MIN_RECALL
                               for x in IMPORTANT_FAULTS)}


def trials():
    yield "baseline_21_scaled", FEATURES, True, "hgb_baseline"
    yield "baseline_21_unscaled", FEATURES, False, "hgb_baseline"
    yield "current_scaled", FEATURES + CURRENT, True, "hgb_baseline"
    yield "current_unscaled", FEATURES + CURRENT, False, "hgb_baseline"
    yield "temporal_scaled", FEATURES + CURRENT + TEMPORAL, True, "hgb_baseline"
    yield "temporal_unscaled", FEATURES + CURRENT + TEMPORAL, False, "hgb_baseline"
    for name in ("hgb_regularized", "hgb_shallow", "extra_trees"):
        yield "temporal_" + name, FEATURES + CURRENT + TEMPORAL, True, name


def select():
    assert not (OUT / "selection.json").exists(), "Selection already frozen"
    splits = load()
    manifest = splits.manifest
    fit = matrix(splits.fit, FEATURES + CURRENT + TEMPORAL)
    validation = matrix(splits.validation, FEATURES + CURRENT + TEMPORAL)
    y = fit.fault_type
    weights = compute_sample_weight(class_weight="balanced", y=y)
    weights *= y.map({"Cooling_System_Degradation": 5., "Sensor_Drift": 1.6}).fillna(1.).to_numpy()
    results = {}
    for name, features, scaling, estimator in trials():
        model = build(features, scaling, estimator)
        model.fit(fit[features], y, classifier__sample_weight=weights)
        results[name] = {"features": features, "scaling": scaling, "estimator": estimator,
                         "validation": assess(model, validation, features)}
        print(name, results[name]["validation"]["macro_f1"], flush=True)
    selected = max(results, key=lambda x: (results[x]["validation"]["macro_f1"],
                                           results[x]["validation"]["balanced_accuracy"]))
    frozen = {"dataset_sha256": DATA_HASH, "split_manifest": manifest,
              "versions": {"python": platform.python_version(), "sklearn": sklearn.__version__,
                           "numpy": np.__version__, "pandas": pd.__version__, "joblib": joblib.__version__},
              "weights": "balanced inverse class frequency; cooling x5; sensor drift x1.6",
              "gate": {"minimum_per_fault_recall": MIN_RECALL,
                       "required_splits": ["validation", "challenge", "time_forward"]},
              "selection_rule": "validation macro F1 then balanced accuracy",
              "audit_previously_inspected": True,
              "selected": selected, "trials": results}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "selection.json").write_text(json.dumps(frozen, indent=2))
    print("FROZEN", selected)


def audit():
    selection_path = OUT / "selection.json"
    assert selection_path.exists(), "Freeze selection first"
    assert not (OUT / "final_audit.json").exists(), "Audit already performed"
    selection = json.loads(selection_path.read_text())
    splits = load()
    assert selection["dataset_sha256"] == DATA_HASH and selection["split_manifest"] == splits.manifest
    selected = selection["trials"][selection["selected"]]
    features = selected["features"]
    fit = matrix(splits.fit, features)
    y = fit.fault_type
    weights = compute_sample_weight(class_weight="balanced", y=y)
    weights *= y.map({"Cooling_System_Degradation": 5., "Sensor_Drift": 1.6}).fillna(1.).to_numpy()
    model = build(features, selected["scaling"], selected["estimator"])
    model.fit(fit[features], y, classifier__sample_weight=weights)
    assessments = {name: assess(model, matrix(getattr(splits, name), features), features)
                   for name in ("validation", "challenge", "time_forward")}
    gate = (all(v["recall_gate"] for v in assessments.values())
            and all(splits.manifest["engine_disjoint"].values())
            and splits.manifest["mission_disjoint"])
    result = {"selection_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
              "selected": selection["selected"], "assessments": assessments,
              "release_gate_passed": bool(gate), "status": "NOT_VALIDATED" if not gate else "VALIDATED_CANDIDATE",
              "probability_status": "NOT_CALIBRATED", "audit_previously_inspected": True}
    (OUT / "final_audit.json").write_text(json.dumps(result, indent=2))
    joblib.dump({"model": model, "features": features, "selection_sha256": result["selection_sha256"],
                 "release_gate_passed": gate}, OUT / "research_model.joblib")
    print("GATE", "PASS" if gate else "FAIL")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("select", "audit"))
    args = parser.parse_args()
    select() if args.stage == "select" else audit()
