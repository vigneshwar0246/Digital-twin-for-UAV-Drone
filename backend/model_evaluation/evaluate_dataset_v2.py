"""Stage 2 & Stage 3: Dataset v2 Model Retraining and Controlled Evaluation.

Implements:
1. Environment & dataset integrity verification (v1 hash, v2 hash, manifest hash).
2. Four-partition protocol via build_evaluation_splits:
   - fit (134 missions, 14 engines)
   - time_forward (34 missions, 14 engines) [Known-engine temporal generalization]
   - validation (36 missions, 3 unseen engines) [Unseen-engine candidate selection]
   - challenge (36 missions, 3 unseen engines) [Unseen-engine final audit]
   plus known-engine validation partition (generator split).
3. Four controlled candidates:
   - c1_raw_telemetry: Raw instantaneous features (ml_features contract).
   - c2_raw_plus_derived: Raw + instantaneous physical spreads and residuals.
   - c3_full_causal_unweighted: Candidate 2 + rolling causal temporal features.
   - c4_full_causal_safety_weighted: Candidate 3 + established reference safety cost.
4. Comprehensive metrics:
   - Accuracy, Balanced Accuracy, Macro F1, Weighted F1, Per-Class P/R/F1.
   - Confusion matrices, error analyses, PR curves, ECE calibration.
   - In-depth cooling fault breakdown by severity, cylinder, and false-negative destinations.
   - Release gate evaluation (0.80 recall for every required fault class on every partition).
5. Output isolation: all artifacts saved to backend/model_evaluation/outputs_v2/.
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
from sklearn.preprocessing import OneHotEncoder, StandardScaler, label_binarize
from sklearn.utils.class_weight import compute_sample_weight

from backend.app.ml_features import FEATURES as RAW_FEATURES, NUMERIC_FEATURES as RAW_NUMERIC
from .evaluation_protocol import build_evaluation_splits
from .evaluation_metrics import evaluate_predictions, error_analyses, precision_recall_rows

ROOT = Path(__file__).resolve().parents[2]
DATA_V1_PATH = ROOT / "backend" / "dataset" / "data" / "aero_engine_full.csv"
DATA_V2_DIR = ROOT / "backend" / "dataset" / "dataset_v2" / "data"
DATA_V2_FULL = DATA_V2_DIR / "aero_engine_full.csv"
MANIFEST_V2 = DATA_V2_DIR / "mission_manifest.json"

OUTPUT_DIR_V2 = Path(__file__).resolve().parent / "outputs_v2"
REPORT_DIR_V2 = OUTPUT_DIR_V2 / "reports"
GRAPH_DIR_V2 = OUTPUT_DIR_V2 / "graphs"
MODEL_DIR_V2 = OUTPUT_DIR_V2 / "models"

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

DERIVED_INSTANTANEOUS = [
    "cht_spread_c",
    "egt_spread_c",
    "cht_mean_c",
    "egt_mean_c",
    "cht_upper_pair_spread_c",
    "cht_lower_pair_spread_c",
    "cht_load_residual_c",
    "cht_egt_gap_c",
    "cht_peak_over_median_c",
]

TEMPORAL_ROLLING = [
    "rpm_delta",
    "rpm_rolling_std_7",
    "rpm_rolling_std_21",
    "vibration_rms_delta",
    "vibration_rms_rolling_std_7",
    "vibration_rms_rolling_std_21",
    "cht_mean_c_delta",
    "cht_mean_c_rolling_std_7",
    "cht_mean_c_rolling_std_21",
    "egt_mean_c_delta",
    "egt_mean_c_rolling_std_7",
    "egt_mean_c_rolling_std_21",
    "cht_spread_c_rolling_mean_21",
    "egt_spread_c_rolling_mean_21",
    "cht_load_residual_c_delta",
    "cht_load_residual_c_rolling_mean_21",
    "oil_temperature_c_delta",
    "oil_temperature_c_rolling_mean_21",
    "cht_rise_rate_c_per_s",
]


def compute_derived_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute instantaneous and causal rolling features strictly respecting mission boundaries."""
    df = frame.sort_values(["mission_id", "time_seconds"]).copy()

    # 1. Instantaneous features
    cht = [f"cylinder_head_temp_{i}_c" for i in range(1, 5)]
    egt = [f"exhaust_gas_temp_{i}_c" for i in range(1, 5)]
    df["cht_spread_c"] = df[cht].max(axis=1) - df[cht].min(axis=1)
    df["egt_spread_c"] = df[egt].max(axis=1) - df[egt].min(axis=1)
    df["cht_mean_c"] = df[cht].mean(axis=1)
    df["egt_mean_c"] = df[egt].mean(axis=1)

    ordered = np.sort(df[cht].to_numpy(), axis=1)
    df["cht_upper_pair_spread_c"] = ordered[:, 3] - ordered[:, 1]
    df["cht_lower_pair_spread_c"] = ordered[:, 2] - ordered[:, 0]
    df["cht_load_residual_c"] = (
        df["cht_mean_c"]
        - df["ambient_temperature_c"]
        - 1.25 * df["engine_load_percent"]
        - 0.0014 * df["altitude_m"]
    )
    df["cht_egt_gap_c"] = df["cht_mean_c"] - df["egt_mean_c"]
    df["cht_peak_over_median_c"] = ordered[:, 3] - np.median(ordered, axis=1)

    # 2. Causal rolling temporal features (grouped per mission)
    grouped = df.groupby("mission_id", sort=False)
    for col in ("rpm", "vibration_rms", "cht_mean_c", "egt_mean_c"):
        df[f"{col}_delta"] = grouped[col].diff().fillna(0)
        for w in (7, 21):
            df[f"{col}_rolling_std_{w}"] = (
                grouped[col]
                .rolling(w, min_periods=2)
                .std()
                .reset_index(level=0, drop=True)
                .fillna(0)
            )

    for col in ("cht_spread_c", "egt_spread_c"):
        df[f"{col}_rolling_mean_21"] = (
            grouped[col]
            .rolling(21, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )

    for col in ("cht_load_residual_c", "oil_temperature_c"):
        df[f"{col}_delta"] = grouped[col].diff().fillna(0)
        df[f"{col}_rolling_mean_21"] = (
            grouped[col]
            .rolling(21, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )

    dt = grouped["time_seconds"].diff().replace(0, np.nan).fillna(1)
    df["cht_rise_rate_c_per_s"] = df["cht_mean_c_delta"] / dt

    return df


def plot_matrix(matrix, labels, title, filepath, normalized=False):
    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=1 if normalized else None)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set(
        xticks=np.arange(len(labels)),
        yticks=np.arange(len(labels)),
        xticklabels=labels,
        yticklabels=labels,
        xlabel="Predicted class",
        ylabel="Actual class",
        title=title,
    )
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fmt = ".2f" if normalized else "d"
    thresh = matrix.max() / 2 if matrix.size else 0
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(
                j,
                i,
                format(matrix[i, j], fmt),
                ha="center",
                va="center",
                fontsize=7,
                color="white" if matrix[i, j] > thresh else "black",
            )
    fig.tight_layout()
    fig.savefig(filepath, dpi=160)
    plt.close(fig)


def train_and_evaluate_candidate(
    cand_name: str,
    feature_list: list,
    use_safety_weights: bool,
    splits_dict: dict,
    all_classes: list,
):
    """Train candidate on fit, evaluate on validation, challenge, time_forward, and known_engine."""
    fit_df = splits_dict["fit"]
    val_df = splits_dict["validation"]
    chal_df = splits_dict["challenge"]
    tf_df = splits_dict["time_forward"]
    ke_val_df = splits_dict.get("known_engine_val")

    cat_cols = ["mission_phase"]
    num_cols = [c for c in feature_list if c not in cat_cols]

    processor = ColumnTransformer(
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
    pipe = Pipeline([("proc", processor), ("clf", clf)])

    sample_weights = compute_sample_weight(class_weight="balanced", y=fit_df[TARGET])
    if use_safety_weights:
        safety_map = {"Cooling_System_Degradation": 5.0, "Sensor_Drift": 1.6}
        sample_weights *= fit_df[TARGET].map(safety_map).fillna(1.0).to_numpy()

    t0 = time.perf_counter()
    pipe.fit(fit_df[feature_list], fit_df[TARGET], clf__sample_weight=sample_weights)
    train_time = time.perf_counter() - t0

    model_classes = list(pipe.named_steps["clf"].classes_)

    results = {
        "candidate": cand_name,
        "features": feature_list,
        "feature_count": len(feature_list),
        "use_safety_weights": use_safety_weights,
        "train_time_seconds": train_time,
        "partitions": {},
    }

    eval_splits = [
        ("validation", val_df),
        ("challenge", chal_df),
        ("time_forward", tf_df),
    ]
    if ke_val_df is not None:
        eval_splits.append(("known_engine_val", ke_val_df))

    for part_name, p_df in eval_splits:
        proba = pipe.predict_proba(p_df[feature_list])
        preds = np.asarray(model_classes)[np.argmax(proba, axis=1)]
        metrics, report, binary = evaluate_predictions(
            p_df[TARGET], preds, proba, model_classes
        )

        recall_checks = {
            cls: bool(
                metrics["per_class"][cls]["support"] > 0
                and metrics["per_class"][cls]["recall"] >= MIN_RECALL
            )
            for cls in IMPORTANT_FAULTS
        }
        all_important_passed = all(recall_checks.values())

        metrics["recall_requirement"] = {
            "threshold": MIN_RECALL,
            "per_class_pass": recall_checks,
            "passed": all_important_passed,
        }
        results["partitions"][part_name] = metrics

        # Confusion matrices
        raw_cm = confusion_matrix(p_df[TARGET], preds, labels=model_classes)
        norm_cm = confusion_matrix(
            p_df[TARGET], preds, labels=model_classes, normalize="true"
        )

        cm_raw_df = pd.DataFrame(raw_cm, index=model_classes, columns=model_classes)
        cm_norm_df = pd.DataFrame(norm_cm, index=model_classes, columns=model_classes)

        cm_raw_df.to_csv(
            REPORT_DIR_V2 / f"{cand_name}_{part_name}_confusion_matrix.csv"
        )
        cm_norm_df.to_csv(
            REPORT_DIR_V2 / f"{cand_name}_{part_name}_confusion_matrix_normalized.csv"
        )
        pd.DataFrame(report).T.to_csv(
            REPORT_DIR_V2 / f"{cand_name}_{part_name}_classification_report.csv"
        )

        plot_matrix(
            raw_cm,
            model_classes,
            f"{cand_name} — {part_name.replace('_', ' ').title()} CM",
            GRAPH_DIR_V2 / f"{cand_name}_{part_name}_confusion_matrix.png",
        )
        plot_matrix(
            norm_cm,
            model_classes,
            f"{cand_name} — {part_name.replace('_', ' ').title()} Normalized CM",
            GRAPH_DIR_V2 / f"{cand_name}_{part_name}_confusion_matrix_normalized.png",
            normalized=True,
        )

        # Precision-Recall curves
        pr_df = precision_recall_rows(binary, proba, model_classes)
        pr_df.to_csv(
            REPORT_DIR_V2 / f"{cand_name}_{part_name}_pr_curves.csv", index=False
        )

    # Save model artifact
    joblib.dump(pipe, MODEL_DIR_V2 / f"{cand_name}.joblib")
    return results, pipe


def analyze_cooling_details(model, features, test_df, partition_name, manifest_df):
    """Detailed diagnosis of Cooling System Degradation: severity, cylinder, false negatives."""
    model_classes = list(model.named_steps["clf"].classes_)
    proba = model.predict_proba(test_df[features])
    preds = np.asarray(model_classes)[np.argmax(proba, axis=1)]

    eval_df = test_df.copy()
    eval_df["predicted"] = preds

    # Join with manifest metadata to get affected_cylinder
    if "affected_cylinder" not in eval_df.columns and manifest_df is not None:
        cyl_map = manifest_df.set_index("mission_id")["affected_cylinder"].to_dict()
        eval_df["affected_cylinder"] = eval_df["mission_id"].map(cyl_map)

    cooling_mask = eval_df[TARGET] == "Cooling_System_Degradation"
    cooling_samples = eval_df[cooling_mask]

    overall_recall = float((cooling_samples["predicted"] == "Cooling_System_Degradation").mean())
    by_sev = {}
    for sev in ["Low", "Medium", "High"]:
        sev_sub = cooling_samples[cooling_samples["fault_severity"] == sev]
        if len(sev_sub) > 0:
            by_sev[sev] = {
                "support": len(sev_sub),
                "recall": float((sev_sub["predicted"] == "Cooling_System_Degradation").mean()),
                "predicted_counts": sev_sub["predicted"].value_counts().to_dict(),
            }

    by_cyl = {}
    if "affected_cylinder" in cooling_samples.columns:
        for cyl in [0, 1, 2, 3]:
            cyl_sub = cooling_samples[cooling_samples["affected_cylinder"] == cyl]
            if len(cyl_sub) > 0:
                by_cyl[f"Cylinder_{cyl + 1}"] = {
                    "support": len(cyl_sub),
                    "recall": float((cyl_sub["predicted"] == "Cooling_System_Degradation").mean()),
                    "predicted_counts": cyl_sub["predicted"].value_counts().to_dict(),
                }

    # Confusion breakdown for Cooling
    fn_samples = cooling_samples[cooling_samples["predicted"] != "Cooling_System_Degradation"]
    fn_destinations = fn_samples["predicted"].value_counts().to_dict()

    return {
        "partition": partition_name,
        "total_cooling_samples": len(cooling_samples),
        "overall_recall": overall_recall,
        "by_severity": by_sev,
        "by_cylinder": by_cyl,
        "false_negative_destinations": fn_destinations,
    }


def main():
    for d in (REPORT_DIR_V2, GRAPH_DIR_V2, MODEL_DIR_V2):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Environment & hashes
    v1_hash = hashlib.sha256(DATA_V1_PATH.read_bytes()).hexdigest()
    v2_hash = hashlib.sha256(DATA_V2_FULL.read_bytes()).hexdigest()
    manifest_hash = hashlib.sha256(MANIFEST_V2.read_bytes()).hexdigest()

    manifest_data = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))
    manifest_df = pd.DataFrame(manifest_data["missions"])

    print(f"Dataset v1 SHA256: {v1_hash}")
    print(f"Dataset v2 SHA256: {v2_hash}")
    print(f"Manifest SHA256:   {manifest_hash}")

    # 2. Build four-part splits via build_evaluation_splits
    full_df = pd.read_csv(DATA_V2_FULL, keep_default_na=False)
    splits = build_evaluation_splits(full_df, TARGET, SEED)

    # Also load the known-engine validation set
    known_eng_val = pd.read_csv(
        DATA_V2_DIR / "aero_engine_validation.csv", keep_default_na=False
    )

    # 3. Add derived and causal features
    print("Computing derived features across partitions...")
    splits_featured = {
        "fit": compute_derived_features(splits.fit),
        "validation": compute_derived_features(splits.validation),
        "challenge": compute_derived_features(splits.challenge),
        "time_forward": compute_derived_features(splits.time_forward),
        "known_engine_val": compute_derived_features(known_eng_val),
    }

    # Save split manifest
    (REPORT_DIR_V2 / "split_manifest_v2.json").write_text(
        json.dumps(splits.manifest, indent=2), encoding="utf-8"
    )

    # 4. Candidates definition
    c1_features = list(RAW_FEATURES)
    c2_features = list(RAW_FEATURES) + DERIVED_INSTANTANEOUS
    c3_features = list(RAW_FEATURES) + DERIVED_INSTANTANEOUS + TEMPORAL_ROLLING
    c4_features = list(RAW_FEATURES) + DERIVED_INSTANTANEOUS + TEMPORAL_ROLLING

    candidates_def = [
        ("c1_raw_telemetry", c1_features, False),
        ("c2_raw_plus_derived", c2_features, False),
        ("c3_full_causal_unweighted", c3_features, False),
        ("c4_full_causal_safety_weighted", c4_features, True),
    ]

    all_candidate_results = {}
    models_dict = {}

    all_classes = sorted(full_df[TARGET].unique())

    comparison_rows = []

    for name, feats, use_sw in candidates_def:
        print(f"\n--- Training & Evaluating: {name} (features={len(feats)}, safety_weight={use_sw}) ---")
        res, model = train_and_evaluate_candidate(
            name, feats, use_sw, splits_featured, all_classes
        )
        all_candidate_results[name] = res
        models_dict[name] = model

        for p_name in ("validation", "challenge", "time_forward", "known_engine_val"):
            p_res = res["partitions"][p_name]
            p_pass = p_res["recall_requirement"]["passed"]
            c_recall = p_res["per_class"]["Cooling_System_Degradation"]["recall"]
            d_recall = p_res["per_class"]["Sensor_Drift"]["recall"]
            comparison_rows.append(
                {
                    "candidate": name,
                    "partition": p_name,
                    "accuracy": p_res["accuracy"],
                    "balanced_accuracy": p_res["balanced_accuracy"],
                    "macro_f1": p_res["macro_f1"],
                    "cooling_recall": c_recall,
                    "sensor_drift_recall": d_recall,
                    "gate_passed": p_pass,
                    "ece": p_res["calibration"]["expected_calibration_error_10_bins"],
                }
            )

    comp_df = pd.DataFrame(comparison_rows)
    comp_df.to_csv(REPORT_DIR_V2 / "candidate_comparison.csv", index=False)

    # 5. Cooling System Degradation Deep Dive
    print("\nRunning Cooling System Degradation Deep Dive...")
    cooling_analysis = {}
    for c_name, (name, feats, _) in zip(models_dict.keys(), candidates_def):
        cooling_analysis[c_name] = {}
        for p_name in ("validation", "challenge", "time_forward", "known_engine_val"):
            det = analyze_cooling_details(
                models_dict[c_name],
                feats,
                splits_featured[p_name],
                p_name,
                manifest_df,
            )
            cooling_analysis[c_name][p_name] = det

    (REPORT_DIR_V2 / "cooling_deep_dive.json").write_text(
        json.dumps(cooling_analysis, indent=2), encoding="utf-8"
    )

    # 6. Overall Metrics Summary
    summary_out = {
        "environment": {
            "python": sklearn.__version__,
            "sklearn": sklearn.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
        },
        "datasets": {
            "v1_sha256": v1_hash,
            "v2_sha256": v2_hash,
            "manifest_sha256": manifest_hash,
        },
        "splits_manifest": splits.manifest,
        "candidate_results": all_candidate_results,
    }
    (REPORT_DIR_V2 / "metrics_summary_v2.json").write_text(
        json.dumps(summary_out, indent=2), encoding="utf-8"
    )

    print("\n========================================================")
    print("CANDIDATE COMPARISON SUMMARY:")
    print("========================================================")
    print(comp_df.to_string(index=False))


if __name__ == "__main__":
    main()
