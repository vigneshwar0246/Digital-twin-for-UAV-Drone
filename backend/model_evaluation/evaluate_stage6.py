"""Stage 6: Controlled Cruise-Baseline Calibration Experiment.

Tests whether in-flight per-cylinder cruise baseline normalization improves
incipient cooling detection without increasing false alarms or introducing leakage.

Key safeguards:
1. Isolated outputs under backend/model_evaluation/outputs_stage6/.
2. Causal baseline computation: Evaluates telemetry frame-by-frame. Cruise baseline
   requires 36 consecutive valid cruise frames (180s). Established baseline is locked
   and subtracted only for subsequent frames (t >= t_lock).
3. Pre-baseline & invalid-baseline fallback: Before lock, or if initial spread exceeds
   threshold (>16 deg C indicating pre-existing fault), baseline is marked invalid,
   delta_CHT_norm defaults to 0.0, and baseline_valid=0 indicator is supplied.
4. Model fitting strictly uses fit data only.
5. Candidate selection uses validation only; challenge and time-forward remain frozen audit.
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
from .evaluate_stage4 import compute_detection_delay_and_far

ROOT = Path(__file__).resolve().parents[2]
DATA_V2_DIR = ROOT / "backend" / "dataset" / "dataset_v2" / "data"
DATA_V2_FULL = DATA_V2_DIR / "aero_engine_full.csv"
MANIFEST_V2 = DATA_V2_DIR / "mission_manifest.json"

OUT_STAGE6 = Path(__file__).resolve().parent / "outputs_stage6"
REPORT_DIR = OUT_STAGE6 / "reports"
GRAPH_DIR = OUT_STAGE6 / "graphs"
MODEL_DIR = OUT_STAGE6 / "models"

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

CRUISE_NORM_FEATURES = [
    "delta_cht_1_cruise_norm",
    "delta_cht_2_cruise_norm",
    "delta_cht_3_cruise_norm",
    "delta_cht_4_cruise_norm",
    "cruise_cht_spread_norm",
    "cruise_cht_max_norm",
    "cruise_baseline_valid",
]


def compute_causal_cruise_baseline_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute strictly causal in-flight cruise baseline features per mission.

    Inference-time logic:
    - Frames are processed in forward time order within each mission.
    - An initial 180s (36 frames) of cruise is accumulated if:
      mission_phase == 'cruise', throttle between 55% and 80%, load between 45% and 75%.
    - If spread during accumulation exceeds 16.0 deg C (fault already present), baseline is rejected.
    - Once 36 frames are accumulated and valid, freeze per-cylinder cruise average.
    - All subsequent frames compute: delta_cht_c = CHT_c(t) - cruise_baseline_c.
    - Before lock, or if invalid, delta_cht_c = 0.0 and cruise_baseline_valid = 0.
    """
    df = compute_derived_features(frame)
    df = df.sort_values(["mission_id", "time_seconds"]).reset_index(drop=True)

    cht_cols = [f"cylinder_head_temp_{i}_c" for i in range(1, 5)]

    # Initialize new columns
    for col in CRUISE_NORM_FEATURES:
        df[col] = 0.0

    grouped_indices = df.groupby("mission_id", sort=False).indices

    for mid, idxs in grouped_indices.items():
        m_cht = df.loc[idxs, cht_cols].to_numpy()
        m_phase = df.loc[idxs, "mission_phase"].to_numpy()
        m_throttle = df.loc[idxs, "throttle_percent"].to_numpy()
        m_load = df.loc[idxs, "engine_load_percent"].to_numpy()

        n_samples = len(idxs)
        accumulated_cht = []
        baseline = None
        is_valid = False

        norm_cht = np.zeros((n_samples, 4))
        spread_norm = np.zeros(n_samples)
        max_norm = np.zeros(n_samples)
        valid_flag = np.zeros(n_samples)

        for i in range(n_samples):
            if baseline is None:
                # Check if current frame qualifies as steady cruise
                is_cruise = (
                    m_phase[i] == "cruise"
                    and 55.0 <= m_throttle[i] <= 80.0
                    and 45.0 <= m_load[i] <= 75.0
                )
                if is_cruise:
                    accumulated_cht.append(m_cht[i])
                    if len(accumulated_cht) == 36:  # 180s reached
                        accum_arr = np.asarray(accumulated_cht)
                        # Sanity check: is initial spread already abnormally high?
                        mean_spread = np.mean(accum_arr.max(axis=1) - accum_arr.min(axis=1))
                        if mean_spread <= 16.0:
                            baseline = np.mean(accum_arr, axis=0)
                            is_valid = True
                        else:
                            # Pre-existing anomaly detected during baseline accumulation; reject baseline
                            baseline = None
                            is_valid = False

            if baseline is not None and is_valid:
                # Baseline is locked! Compute relative deviations
                diff = m_cht[i] - baseline
                norm_cht[i] = diff
                spread_norm[i] = diff.max() - diff.min()
                max_norm[i] = diff.max()
                valid_flag[i] = 1.0
            else:
                # Pre-baseline or invalid fallback
                norm_cht[i] = 0.0
                spread_norm[i] = 0.0
                max_norm[i] = 0.0
                valid_flag[i] = 0.0

        for c_idx in range(4):
            df.loc[idxs, f"delta_cht_{c_idx+1}_cruise_norm"] = norm_cht[:, c_idx]
        df.loc[idxs, "cruise_cht_spread_norm"] = spread_norm
        df.loc[idxs, "cruise_cht_max_norm"] = max_norm
        df.loc[idxs, "cruise_baseline_valid"] = valid_flag

    return df


def evaluate_pipeline(
    name: str,
    feature_list: list,
    splits_dict: dict,
    all_classes: list,
    manifest_df: pd.DataFrame,
):
    """Fit pipeline on fit data only, evaluate across validation, challenge, time-forward, known-engine."""
    fit_df = splits_dict["fit"]
    val_df = splits_dict["validation"]
    chal_df = splits_dict["challenge"]
    tf_df = splits_dict["time_forward"]
    ke_val_df = splits_dict["known_engine_val"]

    cat_cols = ["mission_phase"]
    num_cols = [c for c in feature_list if c not in cat_cols]

    proc = ColumnTransformer(
        [
            ("num", StandardScaler(), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
        ]
    )
    clf = HistGradientBoostingClassifier(
        max_iter=220,
        learning_rate=0.075,
        max_leaf_nodes=31,
        l2_regularization=0.5,
        random_state=SEED,
    )
    pipe = Pipeline([("proc", proc), ("clf", clf)])

    w = compute_sample_weight(class_weight="balanced", y=fit_df[TARGET])
    w *= fit_df[TARGET].map({"Cooling_System_Degradation": 5.0, "Sensor_Drift": 1.6}).fillna(1.0).to_numpy()

    t0 = time.perf_counter()
    pipe.fit(fit_df[feature_list], fit_df[TARGET], clf__sample_weight=w)
    train_time = time.perf_counter() - t0

    model_path = MODEL_DIR / f"{name}.joblib"
    joblib.dump(pipe, model_path)

    results = {
        "candidate": name,
        "features": feature_list,
        "train_time_s": train_time,
        "partitions": {},
        "cooling_diagnostics": {},
    }

    eval_splits = [
        ("validation", val_df),
        ("challenge", chal_df),
        ("time_forward", tf_df),
        ("known_engine_val", ke_val_df),
    ]

    for p_name, p_df in eval_splits:
        proba = pipe.predict_proba(p_df[feature_list])
        preds = np.asarray(all_classes)[np.argmax(proba, axis=1)]

        metrics, report, binary = evaluate_predictions(p_df[TARGET], preds, proba, all_classes)
        far_stats = compute_detection_delay_and_far(p_df, preds)
        metrics["timing_and_alarms"] = far_stats

        recall_checks = {
            cls: bool(
                metrics["per_class"][cls]["support"] > 0
                and metrics["per_class"][cls]["recall"] >= MIN_RECALL
            )
            for cls in IMPORTANT_FAULTS
        }
        metrics["recall_requirement"] = {
            "threshold": MIN_RECALL,
            "per_class_pass": recall_checks,
            "passed": all(recall_checks.values()),
        }

        results["partitions"][p_name] = metrics

        # Confusion matrices
        raw_cm = confusion_matrix(p_df[TARGET], preds, labels=all_classes)
        norm_cm = confusion_matrix(p_df[TARGET], preds, labels=all_classes, normalize="true")

        pd.DataFrame(raw_cm, index=all_classes, columns=all_classes).to_csv(
            REPORT_DIR / f"{name}_{p_name}_cm.csv"
        )
        pd.DataFrame(norm_cm, index=all_classes, columns=all_classes).to_csv(
            REPORT_DIR / f"{name}_{p_name}_cm_norm.csv"
        )
        pd.DataFrame(report).T.to_csv(
            REPORT_DIR / f"{name}_{p_name}_class_report.csv"
        )

        plot_matrix(
            raw_cm,
            all_classes,
            f"{name} — {p_name.title()} CM",
            GRAPH_DIR / f"{name}_{p_name}_cm.png",
        )
        plot_matrix(
            norm_cm,
            all_classes,
            f"{name} — {p_name.title()} Normalized CM",
            GRAPH_DIR / f"{name}_{p_name}_cm_norm.png",
            normalized=True,
        )

        cool_det = analyze_cooling_details(pipe, feature_list, p_df, p_name, manifest_df)
        results["cooling_diagnostics"][p_name] = cool_det

    return results, pipe


def main():
    for d in (REPORT_DIR, GRAPH_DIR, MODEL_DIR):
        d.mkdir(parents=True, exist_ok=True)

    print("=== AERION Stage 6: Controlled Cruise-Baseline Calibration Experiment ===")

    # 1. Dataset & Manifest
    full_df = pd.read_csv(DATA_V2_FULL, keep_default_na=False)
    splits = build_evaluation_splits(full_df, TARGET, SEED)
    manifest_data = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))
    manifest_df = pd.DataFrame(manifest_data["missions"])
    all_classes = sorted(full_df[TARGET].unique())

    ke_val_df = pd.read_csv(DATA_V2_DIR / "aero_engine_validation.csv", keep_default_na=False)

    # 2. Feature matrix generation
    print("Computing Baseline Causal Features (Candidate A)...")
    splits_std = {
        "fit": compute_derived_features(splits.fit),
        "validation": compute_derived_features(splits.validation),
        "challenge": compute_derived_features(splits.challenge),
        "time_forward": compute_derived_features(splits.time_forward),
        "known_engine_val": compute_derived_features(ke_val_df),
    }

    print("Computing In-Flight Cruise Baseline Normalized Features (Candidate B_norm)...")
    splits_norm = {
        "fit": compute_causal_cruise_baseline_features(splits.fit),
        "validation": compute_causal_cruise_baseline_features(splits.validation),
        "challenge": compute_causal_cruise_baseline_features(splits.challenge),
        "time_forward": compute_causal_cruise_baseline_features(splits.time_forward),
        "known_engine_val": compute_causal_cruise_baseline_features(ke_val_df),
    }

    # 3. Report baseline coverage across missions
    print("\nAuditing cruise baseline eligibility & coverage...")
    fit_norm = splits_norm["fit"]
    val_norm = splits_norm["validation"]
    chal_norm = splits_norm["challenge"]
    tf_norm = splits_norm["time_forward"]

    cov_summary = {}
    for p_label, p_f in [("fit", fit_norm), ("validation", val_norm), ("challenge", chal_norm), ("time_forward", tf_norm)]:
        m_cov = p_f.groupby("mission_id")["cruise_baseline_valid"].max()
        f_cov = p_f["cruise_baseline_valid"].mean()
        cov_summary[p_label] = {
            "total_missions": int(len(m_cov)),
            "missions_locked": int(m_cov.sum()),
            "mission_coverage_pct": float(m_cov.mean() * 100),
            "frame_coverage_pct": float(f_cov * 100),
        }
        print(f"[{p_label.upper()}] Missions with Locked Baseline: {m_cov.sum()}/{len(m_cov)} ({m_cov.mean()*100:.1f}%), Frames with Active Baseline: {f_cov*100:.1f}%")

    (REPORT_DIR / "baseline_coverage_audit.json").write_text(json.dumps(cov_summary, indent=2), encoding="utf-8")

    # 4. Feature sets
    feats_cand_a = list(RAW_FEATURES) + DERIVED_INSTANTANEOUS + TEMPORAL_ROLLING
    feats_cand_b_norm = list(feats_cand_a) + CRUISE_NORM_FEATURES

    # 5. Evaluate Candidate A (Reproduced Baseline)
    print("\n--- Training & Evaluating Candidate A (Reproduced Baseline, 49 features) ---")
    res_a, pipe_a = evaluate_pipeline(
        "Candidate_A_Reference", feats_cand_a, splits_std, all_classes, manifest_df
    )

    # 6. Evaluate Candidate B_norm (Cruise-Baseline Normalized)
    print("\n--- Training & Evaluating Candidate B_norm (Cruise Normalized, 56 features) ---")
    res_b_norm, pipe_b = evaluate_pipeline(
        "Candidate_B_Cruise_Normalized", feats_cand_b_norm, splits_norm, all_classes, manifest_df
    )

    # 7. Build Comparative Summary Table
    comparison_rows = []
    for cand_id, res in [("Candidate_A_Reference", res_a), ("Candidate_B_Cruise_Normalized", res_b_norm)]:
        for p_name in ["validation", "challenge", "time_forward", "known_engine_val"]:
            p_m = res["partitions"][p_name]
            p_cool = res["cooling_diagnostics"][p_name]
            far_data = p_m["timing_and_alarms"]

            c_rec = p_m["per_class"]["Cooling_System_Degradation"]["recall"]
            d_rec = p_m["per_class"]["Sensor_Drift"]["recall"]
            inj_rec = p_m["per_class"]["Fuel_Injector_Degradation"]["recall"]

            low_cool = p_cool["by_severity"].get("Low", {}).get("recall", 0.0)
            med_cool = p_cool["by_severity"].get("Medium", {}).get("recall", 0.0)
            high_cool = p_cool["by_severity"].get("High", {}).get("recall", 0.0)

            comparison_rows.append({
                "candidate": cand_id,
                "partition": p_name,
                "accuracy": p_m["accuracy"],
                "balanced_accuracy": p_m["balanced_accuracy"],
                "macro_f1": p_m["macro_f1"],
                "cooling_recall_overall": c_rec,
                "cooling_recall_low": low_cool,
                "cooling_recall_med": med_cool,
                "cooling_recall_high": high_cool,
                "sensor_drift_recall": d_rec,
                "fuel_injector_recall": inj_rec,
                "false_alarm_rate": far_data["false_alarm_rate"],
                "mean_delay_s": far_data["mean_detection_delay_seconds"],
                "ece": p_m["calibration"]["expected_calibration_error_10_bins"],
                "gate_passed": p_m["recall_requirement"]["passed"],
            })

    comp_df = pd.DataFrame(comparison_rows)
    comp_df.to_csv(REPORT_DIR / "stage6_candidate_comparison.csv", index=False)

    all_stage6_results = {
        "candidate_a": res_a,
        "candidate_b_cruise_normalized": res_b_norm,
        "coverage_summary": cov_summary,
    }
    (REPORT_DIR / "stage6_full_results.json").write_text(json.dumps(all_stage6_results, indent=2), encoding="utf-8")

    print("\n========================================================")
    print("STAGE 6 CRUISE BASELINE CALIBRATION EXPERIMENT SUMMARY:")
    print("========================================================")
    print(comp_df.to_string(index=False))


if __name__ == "__main__":
    main()
