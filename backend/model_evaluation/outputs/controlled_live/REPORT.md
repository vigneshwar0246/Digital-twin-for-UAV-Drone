# Controlled live-feature experiment — 2026-10-10

## Frozen inputs and environment

- Branch: `feature/ml-diagnostics-integration`; dataset SHA256: `2b9a25ab4600bebb4d3d1d95504e22889ce86714bb680b7e68d524d3cb68041e`.
- Split manifest: unchanged `outputs/reports/split_manifest.json`, seed 26054; validation/challenge engines disjoint; all partitions mission disjoint; time-forward on training engines.
- Weights: balanced inverse class frequency, cooling ×5, sensor drift ×1.6. Gate: every important fault recall at least 0.80 on validation, challenge, and time-forward, with split integrity.
- Python 3.13.9, scikit-learn 1.7.2, NumPy 2.1.3, pandas 2.3.3, joblib 1.5.2. The selected research model is **not** wired into the existing feature-flagged runtime.
- The committed baseline artifact loads without a version warning under scikit-learn 1.7.2. A fresh fit with identical code, data, split, and weights reproduced committed macro F1 exactly: validation 0.648185, challenge 0.750567, time-forward 0.632072. The later 1.9.1 rerun (0.654726, 0.758151, 0.632968) is an environment-specific result, not the reference baseline.
- Challenge and time-forward results had been inspected before this series. `selection.json` records that disclosure. This weakens the independence of the final audit; candidate selection in this series used validation scores only.

## Reproduce

From the repository root, using the scikit-learn 1.7.2 environment:

```powershell
& 'C:\Users\yogap\anaconda3\python.exe' -B -m backend.model_evaluation.controlled_live_experiments select
& 'C:\Users\yogap\anaconda3\python.exe' -B -m pytest -q backend/tests/test_experimental_live_features.py
& 'C:\Users\yogap\anaconda3\python.exe' -B -m backend.model_evaluation.controlled_live_experiments audit
```

`select` refuses to overwrite its frozen selection; `audit` refuses a second run. Use a new output directory for any new experiment series. `selection.json` contains all validation per-class metrics, false positives, and confusion matrices. `final_audit.json` contains the same for the selected candidate on all required partitions. `research_model.joblib` is a research artifact only.

## Validation comparisons

Every row used the same fit/validation split and sample weights. HGB baseline uses the committed 220 iteration, 0.075 learning rate, 31 leaf, 0.5 L2 configuration. The 21-feature scaled row copies the committed numeric scaling and phase encoding, restricted to the existing live contract. Current derived features use only current cylinder temperatures. Temporal features use current/past RPM, vibration, cylinder-head and exhaust temperatures, with mission-reset deltas and rolling windows. Airspeed, air/fuel ratio, and features dependent on them are excluded.

| Trial | Macro F1 | Balanced accuracy | Cooling recall | Gate |
|---|---:|---:|---:|---|
| 21 live features, HGB, scaled | 0.400 | 0.416 | 0.074 | FAIL |
| 21 live features, HGB, unscaled | 0.400 | 0.416 | 0.074 | FAIL |
| Current derived, HGB, scaled | 0.485 | 0.514 | 0.017 | FAIL |
| Current derived, HGB, unscaled | 0.485 | 0.514 | 0.017 | FAIL |
| Current + temporal, HGB, scaled | 0.635 | 0.633 | 0.003 | FAIL |
| Current + temporal, HGB, unscaled | 0.635 | 0.633 | 0.003 | FAIL |
| Current + temporal, regularized HGB | 0.654 | 0.657 | 0.005 | FAIL |
| Current + temporal, shallow HGB **selected** | **0.656** | **0.661** | **0.008** | **FAIL** |
| Current + temporal, Extra Trees | 0.596 | 0.591 | 0.036 | FAIL |

Scaling has negligible effect here, consistent with tree split invariance; the small current-feature difference is numerical. Temporal information explains most of the observed macro F1 gain. These are measured associations in this synthetic dataset, not proof of a unique causal mechanism. The selected configuration was frozen in `selection.json` before the final audit.

## Frozen candidate: final audit

| Split | Macro F1 | Balanced accuracy | Faults below 0.80 recall | Gate |
|---|---:|---:|---|---|
| Validation | 0.656 | 0.661 | Bearing, cooling, injector, lubrication, sensor drift | FAIL |
| Challenge | 0.753 | 0.758 | Bearing, cooling, lubrication | FAIL |
| Time-forward | 0.612 | 0.596 | Bearing, cooling, injector, lubrication, sensor drift | FAIL |

Per-class cells below are **recall / precision**. Exact support, F1, false-positive counts, class order, and full 9×9 confusion matrices are in `final_audit.json`.

| Class | Validation | Challenge | Time-forward |
|---|---:|---:|---:|
| Alternator degradation | .989 / .938 | .987 / .970 | .973 / .983 |
| Bearing wear | .647 / .548 | .598 / .571 | .391 / .455 |
| Combustion instability | .856 / .912 | .888 / .945 | .857 / .881 |
| Cooling degradation | .008 / .025 | .414 / .794 | .180 / .412 |
| Fuel injector degradation | .740 / .548 | .887 / .468 | .600 / .705 |
| Healthy | .937 / .883 | .921 / .902 | .955 / .852 |
| Lubrication degradation | .320 / .734 | .243 / .659 | .416 / .624 |
| Sensor drift | .509 / .702 | .944 / .956 | .074 / .028 |
| Spark-plug misfire | .943 / .815 | .940 / .903 | .914 / .896 |

Cooling's confusion is severe: validation has 7 correct of 873, with 346 predicted Healthy, 253 injector, and 245 sensor drift. Challenge has 620 correct of 1,496, with 380 Healthy and 371 injector. Time-forward has 249 correct of 1,381, with 783 sensor drift and 349 Healthy. This directly supports overlapping observed signatures and distribution sensitivity. It does **not** establish which generator rule or physical mechanism caused the overlap. Combustion recall improved from the raw live-feature model but remains one part of a failing release gate.

## Feature parity and fail-safe checks

The research streaming extractor matched offline values across 1,668 rows from two missions and all 42 selected features (zero mismatches within 1e-8). It rejects missing/NaN sensor values, stale or future samples, duplicate/out-of-order timestamps, and a stream beginning mid-mission; state resets at a mission change. The parity test is in `backend/tests/test_experimental_live_features.py`. The existing runtime still uses its 21-feature contract and engineering-rule/statistical fallback; this research extractor is not connected to inference. Real sensor dropouts, different live sampling rates, and long telemetry gaps have not been validated.

## Root causes and limits

- **Confirmed:** removing the committed baseline's unavailable and temporal features reduces validation macro F1 from 0.648 to 0.400 under the matched baseline configuration. Adding available current features raises it to 0.485; causal history raises it to 0.635. Individual removed features were not isolated, so no single feature can be credited.
- **Confirmed:** scaling does not explain the main loss; controlled scaled/unscaled HGB scores are essentially equal.
- **Confirmed:** cooling and lubrication remain below the 0.80 gate in all required partitions. Cooling is frequently confused with Healthy, injector, and sensor drift; the dominant confusion changes by partition.
- **Confirmed from dataset audit, not changed here:** class labels depend strongly on mission progress; 6,773 Healthy rows carry `fault_severity=Low`; engine and cylinder assignment is coupled to mission index; some fit classes span only two or three engines. These are concerns for generalization and label-boundary analysis, not grounds to alter this frozen audit.
- **Hypothesis:** synthetic fault signature overlap and engine/mission coupling drive the unstable cooling and sensor-drift recalls. A separate dataset-version experiment would need a predeclared generator/label change, new partitions, and new untouched audit data to test this.

**Release decision: FAIL.** No threshold or gate was lowered. The default ML-disabled flag, existing candidate artifact, and engineering-rule/statistical fallback were not changed. This synthetic-data result does not establish calibrated probabilities, flight readiness, or release readiness.
