# Baseline fault-classification evaluation

This evaluation uses the existing mission-disjoint train, validation, and test
CSVs. It predicts `fault_type` from current telemetry and mission phase. IDs,
timestamps, severity, anomaly, health, RUL, reliability, outcome, operating hours,
and cycle count are excluded to prevent direct label or mission-identity leakage.

Run from the repository root:

```powershell
python -m backend.model_evaluation.evaluate_fault_classifier
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
Results apply only to this synthetic dataset and do not establish real-flight
performance or airworthiness.
