"""Cooling recall investigation; selection uses fit and validation only.

Run ``describe``, ``select``, then ``audit`` in that order. Audit is one-shot.
Previously inspected audit partitions are descriptive only until selection freezes.
"""
import argparse
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from sklearn.utils.class_weight import compute_sample_weight

from .controlled_live_experiments import (COOLING_CURRENT, COOLING_TEMPORAL, CURRENT,
    DATA_HASH, FEATURES, HERE, IMPORTANT_FAULTS, MIN_RECALL, TEMPORAL,
    assess, build, load, matrix)

OUT = HERE / "outputs" / "cooling_investigation"
PREVIOUS = HERE / "outputs" / "controlled_live"
COOL = "Cooling_System_Degradation"
BASE = FEATURES + CURRENT + TEMPORAL


def weights(y, cooling_cost):
    return compute_sample_weight(class_weight="balanced", y=y) * y.map(
        {COOL: cooling_cost, "Sensor_Drift": 1.6}).fillna(1.).to_numpy()


def grouped_cooling(frame, pred):
    d = frame.loc[frame.fault_type.eq(COOL), ["engine_id", "mission_id", "fault_severity"]].copy()
    d["predicted"] = pred[frame.fault_type.eq(COOL).to_numpy()]
    def rows(keys):
        out = []
        for group, part in d.groupby(keys, dropna=False):
            if not isinstance(group, tuple): group = (group,)
            out.append({**dict(zip(keys, group)), "support": len(part),
                        "recall": float(part.predicted.eq(COOL).mean()),
                        "predicted_as": {k: int(v) for k, v in part.predicted.value_counts().items()}})
        return out
    return {"by_engine": rows(["engine_id"]), "by_mission": rows(["mission_id"]),
            "by_severity": rows(["fault_severity"]),
            "by_engine_severity": rows(["engine_id", "fault_severity"])}


def describe():
    assert not (OUT / "descriptive.json").exists()
    splits = load()
    saved = joblib.load(PREVIOUS / "research_model.joblib")
    results = {}
    for name in ("validation", "challenge", "time_forward"):
        frame = matrix(getattr(splits, name), saved["features"])
        pred = saved["model"].predict(frame[saved["features"]])
        results[name] = grouped_cooling(frame, pred)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "descriptive.json").write_text(json.dumps({"dataset_sha256": DATA_HASH,
        "model": "previous frozen research candidate", "audit_previously_inspected": True,
        "splits": results}, indent=2))


def trial_definitions():
    # Bounded, predeclared feature, weight, and estimator checks.
    yield "reference", BASE, 5., "hgb_shallow"
    yield "cool_current", BASE + COOLING_CURRENT, 5., "hgb_shallow"
    yield "cool_temporal", BASE + COOLING_CURRENT + COOLING_TEMPORAL, 5., "hgb_shallow"
    yield "cool_temporal_cost10", BASE + COOLING_CURRENT + COOLING_TEMPORAL, 10., "hgb_shallow"
    yield "cool_temporal_cost20", BASE + COOLING_CURRENT + COOLING_TEMPORAL, 20., "hgb_shallow"
    yield "cool_temporal_regularized", BASE + COOLING_CURRENT + COOLING_TEMPORAL, 5., "hgb_regularized"
    yield "cool_temporal_baseline", BASE + COOLING_CURRENT + COOLING_TEMPORAL, 5., "hgb_baseline"
    yield "cool_temporal_trees", BASE + COOLING_CURRENT + COOLING_TEMPORAL, 5., "extra_trees"


def admissible(value, reference):
    # Fixed before validation: avoid exchanging other faults for cooling alerts.
    v = value["validation"]; r = reference["validation"]
    return (v["per_class"][COOL]["recall"] >= .80 and
            v["per_class"][COOL]["precision"] >= .30 and
            v["macro_f1"] >= r["macro_f1"] - .03 and
            all(v["per_class"][c]["recall"] >= r["per_class"][c]["recall"] - .05
                for c in IMPORTANT_FAULTS - {COOL}))


def select():
    assert not (OUT / "selection.json").exists()
    splits = load()
    all_features = BASE + COOLING_CURRENT + COOLING_TEMPORAL
    fit = matrix(splits.fit, all_features)
    validation = matrix(splits.validation, all_features)
    trials = {}
    for name, features, cost, estimator in trial_definitions():
        model = build(features, True, estimator)
        model.fit(fit[features], fit.fault_type,
                  classifier__sample_weight=weights(fit.fault_type, cost))
        metric = assess(model, validation, features)
        trials[name] = {"features": features, "cooling_weight": cost,
                        "estimator": estimator, "validation": metric}
        print(name, round(metric["per_class"][COOL]["recall"], 4),
              round(metric["macro_f1"], 4), flush=True)
    reference = trials["reference"]
    qualified = [name for name, trial in trials.items() if admissible(trial, reference)]
    # Retain reference if none meet the predeclared safety constraints.
    selected = max(qualified, key=lambda n: (trials[n]["validation"]["macro_f1"],
                                            trials[n]["validation"]["balanced_accuracy"])) if qualified else "reference"
    # Inner group checks on fit missions, never audit partitions. These are stability checks,
    # not a source of hyperparameter changes after validation selection.
    inner = {}
    for name in sorted(set(["reference", selected])):
        trial = trials[name]; features = trial["features"]
        folds = []
        for train_idx, test_idx in GroupKFold(n_splits=3).split(fit, fit.fault_type, fit.mission_id):
            train, test = fit.iloc[train_idx], fit.iloc[test_idx]
            model = build(features, True, trial["estimator"])
            model.fit(train[features], train.fault_type,
                      classifier__sample_weight=weights(train.fault_type, trial["cooling_weight"]))
            folds.append(assess(model, test, features))
        inner[name] = folds
    frozen = {"dataset_sha256": DATA_HASH, "split_manifest": splits.manifest,
              "audit_previously_inspected": True,
              "decision_criteria": {"cooling_recall_min": .80, "cooling_precision_min": .30,
                  "macro_f1_max_drop": .03, "other_fault_recall_max_drop": .05,
                  "selection": "highest validation macro F1 then balanced accuracy among admissible; otherwise reference"},
              "selected": selected, "qualified": qualified, "trials": trials, "inner_grouped_fit_checks": inner}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "selection.json").write_text(json.dumps(frozen, indent=2))
    print("FROZEN", selected, "qualified", qualified)


def audit():
    path = OUT / "selection.json"
    assert path.exists() and not (OUT / "final_audit.json").exists()
    frozen = json.loads(path.read_text())
    splits = load()
    assert frozen["dataset_sha256"] == DATA_HASH and frozen["split_manifest"] == splits.manifest
    trial = frozen["trials"][frozen["selected"]]
    features = trial["features"]
    fit = matrix(splits.fit, features)
    model = build(features, True, trial["estimator"])
    model.fit(fit[features], fit.fault_type,
              classifier__sample_weight=weights(fit.fault_type, trial["cooling_weight"]))
    assessments = {name: assess(model, matrix(getattr(splits, name), features), features)
                   for name in ("validation", "challenge", "time_forward")}
    gate = (all(x["recall_gate"] for x in assessments.values()) and
            all(splits.manifest["engine_disjoint"].values()) and splits.manifest["mission_disjoint"])
    result = {"selection_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "selected": frozen["selected"], "audit_previously_inspected": True,
              "assessments": assessments, "release_gate_passed": bool(gate)}
    (OUT / "final_audit.json").write_text(json.dumps(result, indent=2))
    print("GATE", "PASS" if gate else "FAIL")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("describe", "select", "audit"))
    stage = parser.parse_args().stage
    {"describe": describe, "select": select, "audit": audit}[stage]()
