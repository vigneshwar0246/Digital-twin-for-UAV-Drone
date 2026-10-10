"""Render reviewed candidate metrics without retraining or changing holdouts."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .evaluate_fault_classifier import REPORT_DIR, OUTPUT_DIR


def render():
    root = OUTPUT_DIR / "live_candidate"
    candidate = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))
    baseline_path = root / "baseline_rerun.json"
    baseline = json.loads((baseline_path if baseline_path.exists() else REPORT_DIR / "metrics_summary.json").read_text(encoding="utf-8"))
    rows = []
    for split, result in candidate["selected_assessments"].items():
        labels = result["labels"]
        matrix = pd.DataFrame(result["confusion_matrix"], index=labels, columns=labels)
        matrix.to_csv(root / f"{split}_confusion_matrix.csv")
        for label in labels:
            scores = result["per_class"][label]
            tp = int(matrix.loc[label, label])
            false_negative = int(matrix.loc[label].sum() - tp)
            false_positive = int(matrix[label].sum() - tp)
            rows.append({"split": split, "class": label, **scores,
                         "false_positive": false_positive, "false_negative": false_negative})
    report = pd.DataFrame(rows)
    report.to_csv(root / "per_class_report.csv", index=False)
    challenge = report[report.split == "challenge"].set_index("class")
    fig, ax = plt.subplots(figsize=(11, 5))
    challenge[["recall", "f1-score"]].plot.bar(ax=ax, ylim=(0, 1), rot=40)
    ax.axhline(.8, color="red", linestyle="--", label="required recall")
    ax.set_ylabel("Score")
    ax.set_title("Live-compatible candidate: challenge fault detection")
    fig.tight_layout()
    fig.savefig(root / "challenge_recall_f1.png", dpi=150)
    plt.close(fig)
    lines = ["# Live-compatible model comparison", "", "Synthetic dataset only. Neither model passed the release gate.", "",
             "| Split | Metric | Existing offline HGB | Best live-compatible trial |", "|---|---|---:|---:|"]
    for split, result in candidate["selected_assessments"].items():
        for key in ("accuracy", "balanced_accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1"):
            lines.append(f"| {split} | {key} | {baseline[split][key]:.4f} | {result[key]:.4f} |")
        lines.append(f"| {split} | inference ms/sample | not recorded | {result['inference_ms_per_sample']:.4f} |")
    lines.extend(["", "Candidate selected on validation macro F1 only. Challenge and time-forward are audit results, not tuning inputs.",
                  "The original benchmark retains its broader offline feature set and is not live compatible.",
                  f"Selected candidate training time: {candidate['candidates'][candidate['selected']]['training_seconds']:.2f} seconds; baseline training time was not recorded by its evaluator.",
                  "See `evaluation.json` for configuration, dataset hash, split manifest, per-class scores, and confusion matrices.", ""])
    (root / "COMPARISON.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    render()
