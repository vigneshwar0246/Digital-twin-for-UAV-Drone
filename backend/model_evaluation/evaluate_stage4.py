"""Stage 4: Incipient Fault Detection Investigation.

Implements controlled evaluation of four candidates:
- Candidate A (Reference): Existing Candidate 4 (c4_full_causal_safety_weighted).
- Candidate B (Enhanced Causal Features): Candidate A + long-window rolling thermal
  accumulation (60-frame/300s window), cylinder-to-median persistence, and multi-scale thermal rates.
- Candidate C (Two-Stage Architecture):
  * Stage 1: Binary anomaly detector (Healthy vs Any Anomaly) fitted on fit data.
  * Stage 2: 8-class fault isolation model fitted on fault samples of fit data.
  * Hierarchical inference: If P(Anomaly) < tau, predict Healthy; else predict argmax of Stage 2.
- Candidate D (Temporal Persistence Filter):
  * Causal sliding-window persistence filter applied to Candidate A.
  * Requires K positive detections within window W (e.g. 9 of 15 frames = 75s) to trigger fault alarm.
  * Measures false alarm rate (FAR) on Healthy and detection delay on faulty missions.

All models and transformations fit on fit data only.
Validation used for candidate selection; challenge and time-forward preserved for audit.
Outputs saved to backend/model_evaluation/outputs_stage4/.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

from backend.app.ml_features import FEATURES as RAW_FEATURES, NUMERIC_FEATURES as RAW_NUMERIC
from .evaluation_protocol import build_evaluation_splits
from .evaluation_metrics import evaluate_predictions, precision_recall_rows
from .evaluate_dataset_v2 import (
    compute_derived_features,
    DERIVED_INSTANTANEOUS,
    TEMPORAL_ROLLING,
    plot_matrix,
    analyze_cooling_details,
)

ROOT = Path(__file__).resolve().parents[2]
DATA_V2_DIR = ROOT / "backend" / "dataset" / "dataset_v2" / "data"
DATA_V2_FULL = DATA_V2_DIR / "aero_engine_full.csv"
MANIFEST_V2 = DATA_V2_DIR / "mission_manifest.json"

OUT_STAGE4 = Path(__file__).resolve().parent / "outputs_stage4"
REPORT_DIR = OUT_STAGE4 / "reports"
GRAPH_DIR = OUT_STAGE4 / "graphs"
MODEL_DIR = OUT_STAGE4 / "models"

TARGET = "fault_type"
SEED = 26054
MIN_RECALL = 0.80
IMPORTANT_FAULTS = [
    "Alternator_Degradation",
    "Bearing_Wear",
    "Combustion_Instability",
    "Cooling_System_Degradation",
    "Fuel_Injector_Degradation",
    "Lubrication_System_Degradation",
    "Sensor_Drift",
    "Spark_Plug_Misfire",
]

# Additional features for Candidate B
ENHANCED_TEMPORAL = [
    "cht_spread_c_rolling_mean_60",
    "cht_load_residual_c_rolling_mean_60",
    "cht_peak_over_median_rolling_mean_30",
    "cht_mean_c_rolling_delta_15",
    "oil_temperature_c_rolling_mean_60",
]


def compute_enhanced_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute Candidate B enhanced long-window causal features."""
    df = compute_derived_features(frame)
    grouped = df.groupby("mission_id", sort=False)

    df["cht_spread_c_rolling_mean_60"] = (
        grouped["cht_spread_c"]
        .rolling(60, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["cht_load_residual_c_rolling_mean_60"] = (
        grouped["cht_load_residual_c"]
        .rolling(60, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["cht_peak_over_median_rolling_mean_30"] = (
        grouped["cht_peak_over_median_c"]
        .rolling(30, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df["cht_mean_c_rolling_delta_15"] = grouped["cht_mean_c"].diff(15).fillna(0)
    df["oil_temperature_c_rolling_mean_60"] = (
        grouped["oil_temperature_c"]
        .rolling(60, min_periods=1)
        .mean()
        .reset_index(level=0, drop=True)
    )
    return df


def apply_temporal_persistence_filter(
    predictions: np.ndarray,
    mission_ids: np.ndarray,
    window_size: int = 15,
    threshold_count: int = 9,
    labels: list = None,
) -> np.ndarray:
    """Causal sliding-window persistence filter (Candidate D).

    Within each mission:
    A non-Healthy fault class is predicted only if that fault class occurred at least
    `threshold_count` times in the previous `window_size` frames.
    Otherwise, if no fault reaches persistence, output 'Healthy'.
    """
    filtered = np.copy(predictions)
    unique_mids = pd.unique(mission_ids)

    for mid in unique_mids:
        indices = np.where(mission_ids == mid)[0]
        preds_m = predictions[indices]
        n_frames = len(preds_m)

        for i in range(n_frames):
            start = max(0, i - window_size + 1)
            sub_window = preds_m[start : i + 1]

            # Count occurrences of non-healthy classes
            counts = pd.Series(sub_window).value_counts()
            top_fault = None
            for fault_name, count in counts.items():
                if fault_name != "Healthy" and count >= threshold_count:
                    top_fault = fault_name
                    break

            if top_fault is not None:
                filtered[indices[i]] = top_fault
            else:
                # If current raw prediction was Healthy, stay Healthy
                if preds_m[i] == "Healthy":
                    filtered[indices[i]] = "Healthy"
                else:
                    # Transient detection not meeting persistence -> suppress to Healthy
                    filtered[indices[i]] = "Healthy"

    return filtered


def evaluate_predictions_custom(
    y_true: pd.Series,
    y_pred: np.ndarray,
    probabilities: np.ndarray,
    labels: list,
):
    """Evaluate predictions and format results dictionary."""
    metrics, report, binary = evaluate_predictions(y_true, y_pred, probabilities, labels)
    recall_checks = {
        cls: bool(
            metrics["per_class"][cls]["support"] > 0
            and metrics["per_class"][cls]["recall"] >= MIN_RECALL
        )
        for cls in IMPORTANT_FAULTS
    }
    all_passed = all(recall_checks.values())
    metrics["recall_requirement"] = {
        "threshold": MIN_RECALL,
        "per_class_pass": recall_checks,
        "passed": all_passed,
    }
    return metrics, report, binary


def compute_detection_delay_and_far(df: pd.DataFrame, y_pred: np.ndarray):
    """Compute false alarm rate on Healthy and detection delay on faulty missions."""
    df_eval = df.copy()
    df_eval["pred"] = y_pred

    # False alarm rate on genuinely healthy samples
    healthy_mask = df_eval["fault_type"] == "Healthy"
    healthy_samples = df_eval[healthy_mask]
    false_alarms = (healthy_samples["pred"] != "Healthy").sum()
    far = float(false_alarms / len(healthy_samples)) if len(healthy_samples) > 0 else 0.0

    # Detection delay on missions that experience a fault
    delays = []
    faulty_mids = df_eval.loc[df_eval["anomaly_label"] == 1, "mission_id"].unique()

    for mid in faulty_mids:
        m_df = df_eval[df_eval["mission_id"] == mid].sort_values("time_seconds")
        onset_rows = m_df[m_df["anomaly_label"] == 1]
        if onset_rows.empty:
            continue
        onset_time = onset_rows["time_seconds"].iloc[0]

        # First time prediction flagged the fault or any anomaly
        post_onset = m_df[m_df["time_seconds"] >= onset_time]
        detected = post_onset[post_onset["pred"] != "Healthy"]
        if not detected.empty:
            det_time = detected["time_seconds"].iloc[0]
            delays.append(det_time - onset_time)
        else:
            # Never detected in mission
            delays.append(post_onset["time_seconds"].max() - onset_time)

    mean_delay = float(np.mean(delays)) if delays else 0.0
    median_delay = float(np.median(delays)) if delays else 0.0

    return {
        "healthy_samples": len(healthy_samples),
        "false_alarm_count": int(false_alarms),
        "false_alarm_rate": far,
        "faulty_missions_evaluated": len(faulty_mids),
        "mean_detection_delay_seconds": mean_delay,
        "median_detection_delay_seconds": median_delay,
    }


def main():
    for d in (REPORT_DIR, GRAPH_DIR, MODEL_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("=== AERION Stage 4: Incipient Fault Detection Investigation ===")

    # 1. Load Dataset v2 and split protocol
    full_df = pd.read_csv(DATA_V2_FULL, keep_default_na=False)
    splits = build_evaluation_splits(full_df, TARGET, SEED)
    manifest_data = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))
    manifest_df = pd.DataFrame(manifest_data["missions"])
    all_classes = sorted(full_df[TARGET].unique())

    # Known-engine validation
    ke_val_df = pd.read_csv(
        DATA_V2_DIR / "aero_engine_validation.csv", keep_default_na=False
    )

    # 2. Compute feature matrices
    print("Computing standard causal features...")
    splits_std = {
        "fit": compute_derived_features(splits.fit),
        "validation": compute_derived_features(splits.validation),
        "challenge": compute_derived_features(splits.challenge),
        "time_forward": compute_derived_features(splits.time_forward),
        "known_engine_val": compute_derived_features(ke_val_df),
    }

    print("Computing enhanced causal features (Candidate B)...")
    splits_enh = {
        "fit": compute_enhanced_features(splits.fit),
        "validation": compute_enhanced_features(splits.validation),
        "challenge": compute_enhanced_features(splits.challenge),
        "time_forward": compute_enhanced_features(splits.time_forward),
        "known_engine_val": compute_enhanced_features(ke_val_df),
    }

    eval_split_names = [
        ("validation", "validation"),
        ("challenge", "challenge"),
        ("time_forward", "time_forward"),
        ("known_engine_val", "known_engine_val"),
    ]

    # Predeclared features
    feats_std = list(RAW_FEATURES) + DERIVED_INSTANTANEOUS + TEMPORAL_ROLLING
    feats_enh = list(feats_std) + ENHANCED_TEMPORAL

    cat_cols = ["mission_phase"]
    num_std = [c for c in feats_std if c not in cat_cols]
    num_enh = [c for c in feats_enh if c not in cat_cols]

    candidate_results = {}
    candidate_summary_rows = []
    cooling_diagnostics = {}

    # =========================================================================
    # CANDIDATE A: Reference Model (Existing c4_full_causal_safety_weighted)
    # =========================================================================
    print("\n--- Evaluating Candidate A (Reference: c4_full_causal_safety_weighted) ---")
    proc_a = ColumnTransformer(
        [
            ("num", StandardScaler(), num_std),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
        ]
    )
    clf_a = HistGradientBoostingClassifier(
        max_iter=220, learning_rate=0.075, max_leaf_nodes=31, l2_regularization=0.5, random_state=SEED
    )
    pipe_a = Pipeline([("proc", proc_a), ("clf", clf_a)])
    w_a = compute_sample_weight(class_weight="balanced", y=splits_std["fit"][TARGET])
    w_a *= splits_std["fit"][TARGET].map({"Cooling_System_Degradation": 5.0, "Sensor_Drift": 1.6}).fillna(1.0).to_numpy()
    pipe_a.fit(splits_std["fit"][feats_std], splits_std["fit"][TARGET], clf__sample_weight=w_a)
    joblib.dump(pipe_a, MODEL_DIR / "cand_a_reference.joblib")

    candidate_results["Candidate_A"] = {"partitions": {}}
    cooling_diagnostics["Candidate_A"] = {}

    cand_a_preds = {}
    for p_key, p_name in eval_split_names:
        p_df = splits_std[p_key]
        proba = pipe_a.predict_proba(p_df[feats_std])
        preds = np.asarray(all_classes)[np.argmax(proba, axis=1)]
        cand_a_preds[p_key] = (proba, preds)

        metrics, report, binary = evaluate_predictions_custom(p_df[TARGET], preds, proba, all_classes)
        candidate_results["Candidate_A"]["partitions"][p_name] = metrics

        far_stats = compute_detection_delay_and_far(p_df, preds)
        metrics["timing_and_alarms"] = far_stats

        c_rec = metrics["per_class"]["Cooling_System_Degradation"]["recall"]
        d_rec = metrics["per_class"]["Sensor_Drift"]["recall"]
        candidate_summary_rows.append({
            "candidate": "Candidate_A_Reference",
            "partition": p_name,
            "accuracy": metrics["accuracy"],
            "balanced_accuracy": metrics["balanced_accuracy"],
            "macro_f1": metrics["macro_f1"],
            "cooling_recall": c_rec,
            "sensor_drift_recall": d_rec,
            "false_alarm_rate": far_stats["false_alarm_rate"],
            "mean_detection_delay_s": far_stats["mean_detection_delay_seconds"],
            "gate_passed": metrics["recall_requirement"]["passed"],
        })

        cool_det = analyze_cooling_details(pipe_a, feats_std, p_df, p_name, manifest_df)
        cooling_diagnostics["Candidate_A"][p_name] = cool_det

    # =========================================================================
    # CANDIDATE B: Enhanced Causal Features (Long-window thermal persistence)
    # =========================================================================
    print("\n--- Training & Evaluating Candidate B (Enhanced Causal Features) ---")
    proc_b = ColumnTransformer(
        [
            ("num", StandardScaler(), num_enh),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
        ]
    )
    clf_b = HistGradientBoostingClassifier(
        max_iter=240, learning_rate=0.075, max_leaf_nodes=31, l2_regularization=0.5, random_state=SEED
    )
    pipe_b = Pipeline([("proc", proc_b), ("clf", clf_b)])
    w_b = compute_sample_weight(class_weight="balanced", y=splits_enh["fit"][TARGET])
    w_b *= splits_enh["fit"][TARGET].map({"Cooling_System_Degradation": 5.0, "Sensor_Drift": 1.6}).fillna(1.0).to_numpy()
    pipe_b.fit(splits_enh["fit"][feats_enh], splits_enh["fit"][TARGET], clf__sample_weight=w_b)
    joblib.dump(pipe_b, MODEL_DIR / "cand_b_enhanced.joblib")

    candidate_results["Candidate_B"] = {"partitions": {}}
    cooling_diagnostics["Candidate_B"] = {}

    for p_key, p_name in eval_split_names:
        p_df = splits_enh[p_key]
        proba = pipe_b.predict_proba(p_df[feats_enh])
        preds = np.asarray(all_classes)[np.argmax(proba, axis=1)]

        metrics, report, binary = evaluate_predictions_custom(p_df[TARGET], preds, proba, all_classes)
        candidate_results["Candidate_B"]["partitions"][p_name] = metrics

        far_stats = compute_detection_delay_and_far(p_df, preds)
        metrics["timing_and_alarms"] = far_stats

        c_rec = metrics["per_class"]["Cooling_System_Degradation"]["recall"]
        d_rec = metrics["per_class"]["Sensor_Drift"]["recall"]
        candidate_summary_rows.append({
            "candidate": "Candidate_B_Enhanced",
            "partition": p_name,
            "accuracy": metrics["accuracy"],
            "balanced_accuracy": metrics["balanced_accuracy"],
            "macro_f1": metrics["macro_f1"],
            "cooling_recall": c_rec,
            "sensor_drift_recall": d_rec,
            "false_alarm_rate": far_stats["false_alarm_rate"],
            "mean_detection_delay_s": far_stats["mean_detection_delay_seconds"],
            "gate_passed": metrics["recall_requirement"]["passed"],
        })

        cool_det = analyze_cooling_details(pipe_b, feats_enh, p_df, p_name, manifest_df)
        cooling_diagnostics["Candidate_B"][p_name] = cool_det

    # =========================================================================
    # CANDIDATE C: Two-Stage Architecture (Anomaly Detector + Fault Isolator)
    # =========================================================================
    print("\n--- Training & Evaluating Candidate C (Two-Stage Architecture) ---")
    fit_df_c = splits_std["fit"].copy()
    fit_df_c["is_anomaly"] = (fit_df_c[TARGET] != "Healthy").astype(int)

    # Stage 1: Binary Anomaly Detector
    proc_c1 = ColumnTransformer(
        [
            ("num", StandardScaler(), num_std),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
        ]
    )
    clf_c1 = HistGradientBoostingClassifier(
        max_iter=180, learning_rate=0.075, max_leaf_nodes=31, l2_regularization=0.5, random_state=SEED
    )
    pipe_c1 = Pipeline([("proc", proc_c1), ("clf", clf_c1)])
    w_c1 = compute_sample_weight(class_weight="balanced", y=fit_df_c["is_anomaly"])
    pipe_c1.fit(fit_df_c[feats_std], fit_df_c["is_anomaly"], clf__sample_weight=w_c1)

    # Stage 2: Fault Isolation Classifier (Trained on Faulty Samples)
    fault_mask_fit = fit_df_c[TARGET] != "Healthy"
    fit_faults = fit_df_c[fault_mask_fit]
    proc_c2 = ColumnTransformer(
        [
            ("num", StandardScaler(), num_std),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
        ]
    )
    clf_c2 = HistGradientBoostingClassifier(
        max_iter=220, learning_rate=0.075, max_leaf_nodes=31, l2_regularization=0.5, random_state=SEED
    )
    pipe_c2 = Pipeline([("proc", proc_c2), ("clf", clf_c2)])
    w_c2 = compute_sample_weight(class_weight="balanced", y=fit_faults[TARGET])
    w_c2 *= fit_faults[TARGET].map({"Cooling_System_Degradation": 4.0, "Sensor_Drift": 1.6}).fillna(1.0).to_numpy()
    pipe_c2.fit(fit_faults[feats_std], fit_faults[TARGET], clf__sample_weight=w_c2)

    stage2_classes = list(pipe_c2.named_steps["clf"].classes_)
    joblib.dump({"stage1": pipe_c1, "stage2": pipe_c2}, MODEL_DIR / "cand_c_two_stage.joblib")

    candidate_results["Candidate_C"] = {"partitions": {}}
    cooling_diagnostics["Candidate_C"] = {}

    # Optimal anomaly threshold selected on validation for high sensitivity: tau = 0.45
    ANOMALY_THRESHOLD = 0.45

    for p_key, p_name in eval_split_names:
        p_df = splits_std[p_key]
        # Stage 1: P(Anomaly)
        p_anomaly_proba = pipe_c1.predict_proba(p_df[feats_std])[:, 1]
        # Stage 2: P(Fault | Anomaly)
        p_iso_proba = pipe_c2.predict_proba(p_df[feats_std])

        # Combined prediction
        preds_c = np.full(len(p_df), "Healthy", dtype=object)
        is_anom = p_anomaly_proba >= ANOMALY_THRESHOLD
        if np.any(is_anom):
            iso_top = np.asarray(stage2_classes)[np.argmax(p_iso_proba[is_anom], axis=1)]
            preds_c[is_anom] = iso_top

        # Combined probability distribution for metrics
        combined_proba = np.zeros((len(p_df), len(all_classes)))
        healthy_idx = all_classes.index("Healthy")
        combined_proba[:, healthy_idx] = 1.0 - p_anomaly_proba
        for s2_idx, s2_cls in enumerate(stage2_classes):
            cls_idx = all_classes.index(s2_cls)
            combined_proba[:, cls_idx] = p_anomaly_proba * p_iso_proba[:, s2_idx]

        metrics, report, binary = evaluate_predictions_custom(p_df[TARGET], preds_c, combined_proba, all_classes)
        candidate_results["Candidate_C"]["partitions"][p_name] = metrics

        far_stats = compute_detection_delay_and_far(p_df, preds_c)
        metrics["timing_and_alarms"] = far_stats

        c_rec = metrics["per_class"]["Cooling_System_Degradation"]["recall"]
        d_rec = metrics["per_class"]["Sensor_Drift"]["recall"]
        candidate_summary_rows.append({
            "candidate": "Candidate_C_Two_Stage",
            "partition": p_name,
            "accuracy": metrics["accuracy"],
            "balanced_accuracy": metrics["balanced_accuracy"],
            "macro_f1": metrics["macro_f1"],
            "cooling_recall": c_rec,
            "sensor_drift_recall": d_rec,
            "false_alarm_rate": far_stats["false_alarm_rate"],
            "mean_detection_delay_s": far_stats["mean_detection_delay_seconds"],
            "gate_passed": metrics["recall_requirement"]["passed"],
        })

        # Custom cooling breakdown for C
        p_df_eval = p_df.copy()
        p_df_eval["predicted"] = preds_c
        c_mask = p_df_eval[TARGET] == "Cooling_System_Degradation"
        c_sub = p_df_eval[c_mask]
        by_sev_c = {}
        for sev in ["Low", "Medium", "High"]:
            s_rows = c_sub[c_sub["fault_severity"] == sev]
            if len(s_rows) > 0:
                by_sev_c[sev] = {
                    "support": len(s_rows),
                    "recall": float((s_rows["predicted"] == "Cooling_System_Degradation").mean()),
                    "predicted_counts": s_rows["predicted"].value_counts().to_dict(),
                }
        cooling_diagnostics["Candidate_C"][p_name] = {
            "partition": p_name,
            "total_cooling_samples": len(c_sub),
            "overall_recall": float((c_sub["predicted"] == "Cooling_System_Degradation").mean()),
            "by_severity": by_sev_c,
            "false_negative_destinations": c_sub[c_sub["predicted"] != "Cooling_System_Degradation"]["predicted"].value_counts().to_dict(),
        }

    # =========================================================================
    # CANDIDATE D: Temporal Persistence Filter (Applied to Candidate A)
    # =========================================================================
    print("\n--- Evaluating Candidate D (Temporal Persistence Filter) ---")
    candidate_results["Candidate_D"] = {"partitions": {}}
    cooling_diagnostics["Candidate_D"] = {}

    for p_key, p_name in eval_split_names:
        p_df = splits_std[p_key]
        raw_proba, raw_preds = cand_a_preds[p_key]

        # Apply causal sliding persistence filter (W=15 frames, K=9 frames)
        filtered_preds = apply_temporal_persistence_filter(
            raw_preds,
            p_df["mission_id"].values,
            window_size=15,
            threshold_count=9,
            labels=all_classes,
        )

        metrics, report, binary = evaluate_predictions_custom(p_df[TARGET], filtered_preds, raw_proba, all_classes)
        candidate_results["Candidate_D"]["partitions"][p_name] = metrics

        far_stats = compute_detection_delay_and_far(p_df, filtered_preds)
        metrics["timing_and_alarms"] = far_stats

        c_rec = metrics["per_class"]["Cooling_System_Degradation"]["recall"]
        d_rec = metrics["per_class"]["Sensor_Drift"]["recall"]
        candidate_summary_rows.append({
            "candidate": "Candidate_D_Temporal_Persistence",
            "partition": p_name,
            "accuracy": metrics["accuracy"],
            "balanced_accuracy": metrics["balanced_accuracy"],
            "macro_f1": metrics["macro_f1"],
            "cooling_recall": c_rec,
            "sensor_drift_recall": d_rec,
            "false_alarm_rate": far_stats["false_alarm_rate"],
            "mean_detection_delay_s": far_stats["mean_detection_delay_seconds"],
            "gate_passed": metrics["recall_requirement"]["passed"],
        })

        p_df_eval = p_df.copy()
        p_df_eval["predicted"] = filtered_preds
        c_mask = p_df_eval[TARGET] == "Cooling_System_Degradation"
        c_sub = p_df_eval[c_mask]
        by_sev_d = {}
        for sev in ["Low", "Medium", "High"]:
            s_rows = c_sub[c_sub["fault_severity"] == sev]
            if len(s_rows) > 0:
                by_sev_d[sev] = {
                    "support": len(s_rows),
                    "recall": float((s_rows["predicted"] == "Cooling_System_Degradation").mean()),
                    "predicted_counts": s_rows["predicted"].value_counts().to_dict(),
                }
        cooling_diagnostics["Candidate_D"][p_name] = {
            "partition": p_name,
            "total_cooling_samples": len(c_sub),
            "overall_recall": float((c_sub["predicted"] == "Cooling_System_Degradation").mean()),
            "by_severity": by_sev_d,
            "false_negative_destinations": c_sub[c_sub["predicted"] != "Cooling_System_Degradation"]["predicted"].value_counts().to_dict(),
        }

    # Save summary tables and reports
    summary_df = pd.DataFrame(candidate_summary_rows)
    summary_df.to_csv(REPORT_DIR / "stage4_candidate_comparison.csv", index=False)
    (REPORT_DIR / "stage4_metrics.json").write_text(
        json.dumps(candidate_results, indent=2), encoding="utf-8"
    )
    (REPORT_DIR / "stage4_cooling_diagnostics.json").write_text(
        json.dumps(cooling_diagnostics, indent=2), encoding="utf-8"
    )

    print("\n========================================================")
    print("STAGE 4 CANDIDATE COMPARISON SUMMARY:")
    print("========================================================")
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
