# Baseline fault-classification evaluation

This evaluation uses the existing mission-disjoint train, validation, and test
CSVs. It predicts `fault_type` from current telemetry and mission phase. IDs,
timestamps, severity, anomaly, health, RUL, reliability, outcome, operating hours,
and cycle count are excluded to prevent direct label or mission-identity leakage.

Run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m backend.model_evaluation.evaluate_fault_classifier
```

The current protocol creates engine-disjoint validation and challenge groups,
uses later missions from the fitting-engine population for a separate
time-forward audit, and verifies mission disjointness. The challenge set contains
unseen engine identities and trajectory-profile fingerprints.

Machine-readable metrics, split manifests, class distributions, calibration,
confusion matrices, precision-recall curves, and false-positive/negative analyses
are written to `outputs/reports`. Graphs are written to `outputs/graphs`.

The saved candidate artifact is accompanied by `MODEL_NOT_FOR_PRODUCTION.txt`.
It must not be connected to live diagnostics while its release gate fails.
Results apply only to this generated dataset and do not establish real-flight
performance or airworthiness.

## Live-compatible candidate audit (October 2026)

The original artifact expects fields absent from the live telemetry API, including
airspeed, manifold pressure, air-fuel ratio, engine efficiency, and mission-relative
time. `python -m backend.model_evaluation.live_candidate` therefore trains a
separate candidate with only the shared `backend/app/ml_features.py` contract:
mission phase and 20 current numeric sensor/operating fields. No rolling or
future-informed features are used. Preprocessing stays inside each sklearn
pipeline. The unchanged `build_evaluation_splits` protocol separates missions,
holds validation and challenge engines apart, and retains the time-forward audit.

Use the repository virtual environment, pinned to scikit-learn 1.9.1, when
training or loading its joblib artifacts. `render_live_candidate` regenerates
CSV/PNG comparison reports from saved metrics without retraining.

Three bounded trials use the same fit partition, inverse-frequency sample
weights, and the existing cooling (5x) and sensor-drift (1.6x) safety costs:
the existing HGB configuration on live fields, a regularized HGB configuration,
and Extra Trees. Selection uses validation macro F1, then balanced accuracy.
The challenge and time-forward partitions are inspected only after selection.

| Split | Existing HGB macro F1 | Best live-compatible macro F1 | Existing balanced accuracy | Live-compatible balanced accuracy |
|---|---:|---:|---:|---:|
| Time-forward | 0.6330 | 0.3727 | 0.6210 | 0.3529 |
| Validation | 0.6547 | 0.4303 | 0.6635 | 0.4347 |
| Challenge | 0.7582 | 0.5090 | 0.7476 | 0.5157 |

The validation-selected trial is HGB with 300 iterations, learning rate 0.045,
15 maximum leaves, 30 minimum samples per leaf, and L2 regularization 2.0.
Challenge cooling recall is 0.155 and sensor-drift recall is 0.974; several
other faults are much weaker. The existing HGB reaches 0.334 and 0.661 on
those classes, respectively. Both fail the unchanged 0.80 gate. The existing
offline model remains the benchmark; this experiment does **not** demonstrate
an improvement. The current rerun of the original evaluator differs slightly
from the previously committed metrics (challenge macro F1 0.7582 versus 0.7506)
despite the same dataset hash and split manifest; environment/library version
differences have not been isolated. Use the current rerun for like-for-like
comparison and do not treat either result as real-world validation.

The experimental artifact and complete per-class/confusion metrics are in
`outputs/live_candidate/`. It is about 5 MB, marked `NOT_VALIDATED`, and has
uncalibrated scores. Only load trusted local joblib files. The backend rejects
feature or class schema mismatches. It does not serve this failed candidate by
default; explicit development override is documented in the root README.
