"""Train and evaluate a reproducible baseline fault classifier.

The split files are mission-disjoint. Label-derived and future-informed columns
are deliberately excluded so the reported scores measure sensor discrimination.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, classification_report,
    confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, label_binarize
from sklearn.utils.class_weight import compute_sample_weight
from .evaluation_protocol import build_evaluation_splits
from .evaluation_metrics import error_analyses, evaluate_predictions, precision_recall_rows

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "dataset" / "data"
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
REPORT_DIR = OUTPUT_DIR / "reports"
GRAPH_DIR = OUTPUT_DIR / "graphs"

TARGET = "fault_type"
EXCLUDED = {
    "timestamp", "mission_id", "engine_id", "operating_hours", "cycle_count",
    "fault_type", "fault_severity", "anomaly_label", "health_index", "rul_hours",
    "mission_reliability_percent", "mission_outcome",
    "mission_profile_id",
}
IMPORTANT_FAULTS = {
    "Spark_Plug_Misfire", "Fuel_Injector_Degradation",
    "Lubrication_System_Degradation", "Cooling_System_Degradation",
    "Bearing_Wear", "Combustion_Instability", "Sensor_Drift",
    "Alternator_Degradation",
}
MIN_RECALL = .80

def load_split(name):
    return pd.read_csv(DATA_DIR / f"aero_engine_{name}.csv", keep_default_na=False)

def add_causal_features(frame):
    """Past/current telemetry only; each rolling window resets per mission."""
    frame=frame.sort_values(["mission_id","time_seconds"]).copy()
    cht=[f"cylinder_head_temp_{i}_c" for i in range(1,5)]
    egt=[f"exhaust_gas_temp_{i}_c" for i in range(1,5)]
    frame["cht_spread_c"]=frame[cht].max(axis=1)-frame[cht].min(axis=1)
    frame["egt_spread_c"]=frame[egt].max(axis=1)-frame[egt].min(axis=1)
    frame["cht_mean_c"]=frame[cht].mean(axis=1); frame["egt_mean_c"]=frame[egt].mean(axis=1)
    ordered_cht=np.sort(frame[cht].to_numpy(),axis=1)
    frame["cht_upper_pair_spread_c"]=ordered_cht[:,3]-ordered_cht[:,1]
    frame["cht_lower_pair_spread_c"]=ordered_cht[:,2]-ordered_cht[:,0]
    frame["cht_cooling_residual_c"]=(frame.cht_mean_c-frame.ambient_temperature_c
        -1.25*frame.engine_load_percent-.0014*frame.altitude_m
        +10*(frame.airspeed_kmh/220).clip(lower=0)**.65)
    grouped=frame.groupby("mission_id",sort=False)
    for col in ["rpm","air_fuel_ratio","vibration_rms","cht_mean_c","egt_mean_c"]:
        frame[f"{col}_delta"]=grouped[col].diff().fillna(0)
        frame[f"{col}_rolling_std_7"]=grouped[col].rolling(7,min_periods=2).std().reset_index(level=0,drop=True).fillna(0)
        frame[f"{col}_rolling_std_21"]=grouped[col].rolling(21,min_periods=2).std().reset_index(level=0,drop=True).fillna(0)
    for col in ["cht_spread_c","egt_spread_c","cht_cooling_residual_c"]:
        frame[f"{col}_rolling_mean_21"]=grouped[col].rolling(21,min_periods=1).mean().reset_index(level=0,drop=True)
    frame["cht_rise_rate_c_per_s"]=frame["cht_mean_c_delta"]/frame.groupby("mission_id").time_seconds.diff().replace(0,np.nan).fillna(1)
    expected_thermal_delta=(1.25*grouped["engine_load_percent"].diff()+.0014*grouped["altitude_m"].diff()-.045*grouped["airspeed_kmh"].diff()).fillna(0)
    frame["cht_response_residual_delta"]=frame["cht_mean_c_delta"]-expected_thermal_delta
    return frame

def metrics_for(y_true, y_pred, probabilities, labels):
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    result = {
        "samples": len(y_true),
        "accuracy": accuracy_score(y_true, y_pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, y_pred),
        "macro_precision": precision_score(y_true, y_pred, average="macro", zero_division=0),
        "macro_recall": recall_score(y_true, y_pred, average="macro", zero_division=0),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "weighted_f1": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        "per_class": {label: report[label] for label in labels},
    }
    try:
        binary = label_binarize(y_true, classes=labels)
        result["macro_roc_auc_ovr"] = roc_auc_score(binary, probabilities, average="macro", multi_class="ovr")
        result["weighted_roc_auc_ovr"] = roc_auc_score(binary, probabilities, average="weighted", multi_class="ovr")
    except ValueError:
        result["macro_roc_auc_ovr"] = None
        result["weighted_roc_auc_ovr"] = None
    return result, report

def plot_matrix(matrix, labels, title, filename, normalized=False):
    fig, ax = plt.subplots(figsize=(11, 9))
    image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=1 if normalized else None)
    fig.colorbar(image, ax=ax, fraction=.046, pad=.04)
    ax.set(xticks=np.arange(len(labels)), yticks=np.arange(len(labels)),
           xticklabels=labels, yticklabels=labels, xlabel="Predicted class",
           ylabel="Actual class", title=title)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fmt = ".2f" if normalized else "d"
    threshold = matrix.max() / 2 if matrix.size else 0
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, format(matrix[i, j], fmt), ha="center", va="center",
                    fontsize=7, color="white" if matrix[i, j] > threshold else "black")
    fig.tight_layout(); fig.savefig(GRAPH_DIR / filename, dpi=170); plt.close(fig)

def evaluate():
    REPORT_DIR.mkdir(parents=True, exist_ok=True); GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    evaluation_started=datetime.now(timezone.utc)
    full=load_split("full")
    splits=build_evaluation_splits(full,TARGET,26054)
    train=add_causal_features(splits.fit); time_forward=add_causal_features(splits.time_forward)
    validation=add_causal_features(splits.validation); challenge=add_causal_features(splits.challenge)
    features = [c for c in train.columns if c not in EXCLUDED]
    categorical = ["mission_phase"]
    numeric = [c for c in features if c not in categorical]
    processor = ColumnTransformer([
        ("numeric", StandardScaler(), numeric),
        ("phase", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
    ])
    model = Pipeline([
        ("features", processor),
        ("classifier", HistGradientBoostingClassifier(max_iter=220, learning_rate=.075,
                                                       max_leaf_nodes=31, l2_regularization=.5,
                                                       random_state=26054)),
    ])
    sample_weights=compute_sample_weight(class_weight="balanced",y=train[TARGET])
    safety_cost={"Cooling_System_Degradation":5.0,"Sensor_Drift":1.6}
    sample_weights*=train[TARGET].map(safety_cost).fillna(1.0).to_numpy()
    model.fit(train[features], train[TARGET], classifier__sample_weight=sample_weights)
    labels = list(model.named_steps["classifier"].classes_)
    training_finished=datetime.now(timezone.utc)
    all_metrics = {
        "model": "HistGradientBoostingClassifier",
        "model_version": "hgb-fault-candidate-v2.0.0",
        "training_dataset_version": "sha256:"+hashlib.sha256((DATA_DIR/"aero_engine_full.csv").read_bytes()).hexdigest(),
        "feature_schema_version": "aero-telemetry-causal-v2",
        "training_timestamp": training_finished.isoformat(),
        "evaluation_timestamp": evaluation_started.isoformat(),
        "random_seed": 26054,
        "features": features,
        "excluded_leakage_columns": sorted(EXCLUDED - {TARGET}),
        "split_strategy": splits.manifest,
        "split_policy": "engine-disjoint validation/challenge; all partitions mission-disjoint; separate time-forward audit on training engines",
        "temporal_feature_policy": "current and past samples only; rolling windows reset per mission",
        "minimum_important_fault_recall": MIN_RECALL,
        "training_weighting": "inverse-frequency weights; additional false-negative cost: Cooling=5.0, Sensor_Drift=1.6",
        "decision_rule": "uncalibrated maximum predicted probability",
        "probability_status": "NOT_CALIBRATED",
        "model_status": "NOT_VALIDATED",
        "release_readiness": "NOT_RELEASE_READY",
    }
    (REPORT_DIR/"split_manifest.json").write_text(json.dumps(splits.manifest,indent=2),encoding="utf-8")
    class_rows=[]
    for split_name,frame in (("fit",train),("time_forward",time_forward),("validation",validation),("challenge",challenge)):
        counts=frame[TARGET].value_counts()
        for label in sorted(full[TARGET].unique()): class_rows.append({"split":split_name,"fault_class":label,"samples":int(counts.get(label,0)),"percentage":float(counts.get(label,0)/len(frame)*100),"engines":int(frame.loc[frame[TARGET].eq(label),"engine_id"].nunique()),"missions":int(frame.loc[frame[TARGET].eq(label),"mission_id"].nunique())})
    pd.DataFrame(class_rows).to_csv(REPORT_DIR/"evaluation_class_distribution.csv",index=False)
    challenge.drop(columns=["mission_profile_id"],errors="ignore").to_csv(DATA_DIR/"aero_engine_challenge.csv",index=False,float_format="%.4f")
    score_rows = []
    split_frames=(("time_forward",time_forward),("validation",validation),("challenge",challenge))
    labels = list(model.named_steps["classifier"].classes_)
    for split_name, frame in split_frames:
        probability=model.predict_proba(frame[features])
        prediction = np.asarray(labels)[np.argmax(probability,axis=1)]
        metrics,report,binary=evaluate_predictions(frame[TARGET],prediction,probability,labels)
        all_metrics[split_name] = metrics
        recall_checks={label:metrics["per_class"][label]["support"]>0 and metrics["per_class"][label]["recall"]>=MIN_RECALL for label in sorted(IMPORTANT_FAULTS)}
        coverage={label:metrics["per_class"][label]["support"]>0 for label in sorted(IMPORTANT_FAULTS)}
        metrics["recall_requirement"]={"threshold":MIN_RECALL,"class_coverage":coverage,"coverage_passed":all(coverage.values()),"per_class_pass":recall_checks,"passed":all(recall_checks.values())}
        pd.DataFrame(report).T.to_csv(REPORT_DIR / f"{split_name}_classification_report.csv")
        raw = confusion_matrix(frame[TARGET], prediction, labels=labels)
        norm = confusion_matrix(frame[TARGET], prediction, labels=labels, normalize="true")
        pd.DataFrame(raw, index=labels, columns=labels).to_csv(REPORT_DIR / f"{split_name}_confusion_matrix.csv")
        pd.DataFrame(norm, index=labels, columns=labels).to_csv(REPORT_DIR / f"{split_name}_confusion_matrix_normalized.csv")
        plot_matrix(raw, labels, f"{split_name.title()} confusion matrix", f"{split_name}_confusion_matrix.png")
        plot_matrix(norm, labels, f"{split_name.title()} normalized confusion matrix", f"{split_name}_confusion_matrix_normalized.png", True)
        errors=error_analyses(frame[TARGET],prediction,labels)
        errors.to_csv(REPORT_DIR/f"{split_name}_false_positive_negative_analysis.csv",index=False)
        pr=precision_recall_rows(binary,probability,labels)
        pr.to_csv(REPORT_DIR/f"{split_name}_precision_recall_curves.csv",index=False)
        fig,ax=plt.subplots(figsize=(10,7))
        for label,curve in pr.groupby("fault_class"): ax.plot(curve.recall,curve.precision,label=label,lw=1.4)
        ax.set(xlabel="Recall",ylabel="Precision",title=f"{split_name.title()} one-vs-rest precision-recall curves",xlim=(0,1),ylim=(0,1)); ax.legend(fontsize=7)
        fig.tight_layout(); fig.savefig(GRAPH_DIR/f"{split_name}_precision_recall_curves.png",dpi=170); plt.close(fig)
        score_rows.append({"split": split_name, **{k:v for k,v in metrics.items() if isinstance(v,(int,float))}})
    all_metrics["test"]=all_metrics["challenge"]
    gate_splits=("time_forward","validation","challenge")
    gate_passed=all(all_metrics[x]["recall_requirement"]["passed"] for x in gate_splits)
    split_integrity=all(splits.manifest["engine_disjoint"].values()) and splits.manifest["mission_disjoint"]
    all_metrics["release_gate"]={"minimum_fault_recall":MIN_RECALL,"required_splits":list(gate_splits),"recall_passed":gate_passed,"split_integrity_passed":split_integrity,"passed":bool(gate_passed and split_integrity)}
    all_metrics["model_status"]="VALIDATED_CANDIDATE" if all_metrics["release_gate"]["passed"] else "NOT_VALIDATED"
    all_metrics["release_readiness"]="RELEASE_CANDIDATE_REQUIRES_REAL_DATA_VALIDATION" if all_metrics["release_gate"]["passed"] else "NOT_RELEASE_READY"
    all_metrics["evaluation_timestamp"]=datetime.now(timezone.utc).isoformat()
    # Preserve legacy test-named reports as aliases of the dedicated challenge set.
    for suffix in ("classification_report.csv","confusion_matrix.csv","confusion_matrix_normalized.csv","false_positive_negative_analysis.csv","precision_recall_curves.csv"):
        (REPORT_DIR/f"test_{suffix}").write_bytes((REPORT_DIR/f"challenge_{suffix}").read_bytes())
    (REPORT_DIR / "metrics_summary.json").write_text(json.dumps(all_metrics, indent=2), encoding="utf-8")
    scores = pd.DataFrame(score_rows).set_index("split")
    scores.to_csv(REPORT_DIR / "score_summary.csv")
    scores[["accuracy","balanced_accuracy","macro_precision","macro_recall","macro_f1","weighted_f1"]].T.plot.bar(figsize=(11,6), ylim=(0,1), rot=25)
    plt.ylabel("Score"); plt.title("Fault-classification scores"); plt.tight_layout(); plt.savefig(GRAPH_DIR/"accuracy_and_f1_scores.png",dpi=170); plt.close()
    per_class = pd.DataFrame({split:{label:data["f1-score"] for label,data in all_metrics[split]["per_class"].items()} for split in gate_splits})
    per_class.plot.bar(figsize=(12,6),ylim=(0,1)); plt.ylabel("F1 score"); plt.title("Per-class F1 scores"); plt.xticks(rotation=40,ha="right"); plt.tight_layout(); plt.savefig(GRAPH_DIR/"per_class_f1_scores.png",dpi=170); plt.close()
    recalls=pd.DataFrame({split:{label:data["recall"] for label,data in all_metrics[split]["per_class"].items()} for split in gate_splits})
    recalls.plot.bar(figsize=(12,6),ylim=(0,1)); plt.axhline(MIN_RECALL,color="red",ls="--",label="minimum 0.80"); plt.ylabel("Recall"); plt.title("Per-class recall requirement"); plt.xticks(rotation=40,ha="right"); plt.legend(); plt.tight_layout(); plt.savefig(GRAPH_DIR/"per_class_recall.png",dpi=170); plt.close()
    artifact={"model":model,"features":features,"metadata":{k:all_metrics[k] for k in ("model_version","training_dataset_version","feature_schema_version","training_timestamp","evaluation_timestamp","split_strategy","model_status","release_readiness","release_gate")},
        "metrics":{k:all_metrics[k] for k in gate_splits}}
    joblib.dump(artifact,OUTPUT_DIR/"fault_classifier_candidate.joblib")
    (OUTPUT_DIR/"MODEL_NOT_FOR_PRODUCTION.txt").write_text(f"MODEL_STATUS={all_metrics['model_status']}\nRELEASE_READINESS={all_metrics['release_readiness']}\nGenerated test data only. Do not use for operational decisions.\n",encoding="utf-8")
    print(json.dumps({k:all_metrics[k] for k in ("model_status","release_readiness","release_gate","time_forward","validation","challenge")}, indent=2))
    return all_metrics

if __name__ == "__main__":
    results=evaluate()
    raise SystemExit(0 if results["release_gate"]["passed"] else 2)
