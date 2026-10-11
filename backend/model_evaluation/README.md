# Baseline fault-classification evaluation

This evaluation uses the existing mission-disjoint train, validation, and test
CSVs. It predicts `fault_type` from current telemetry and mission phase. IDs,
timestamps, severity, anomaly, health, RUL, reliability, outcome, operating hours,
and cycle count are excluded to prevent direct label or mission-identity leakage.

The stored evaluation under `outputs/` is historical evidence. `evaluate_fault_classifier.py`, `live_candidate.py`, and the Stage 4–6 evaluators write to their default output directories, so **do not rerun them merely to verify application startup or tests**. A new experiment needs a separate output directory and the frozen protocol. Read the saved metrics and reports without modifying them.

The current protocol creates engine-disjoint validation and challenge groups,
uses later missions from the fitting-engine population for a separate
time-forward audit, and verifies mission disjointness. The challenge set contains
unseen engine identities and trajectory-profile fingerprints.

Machine-readable metrics, split manifests, class distributions, calibration,
confusion matrices, precision-recall curves, and false-positive/negative analyses
are written to `outputs/reports`. Graphs are written to `outputs/graphs`.

The saved offline benchmark artifact is accompanied by `MODEL_NOT_FOR_PRODUCTION.txt`.
It is not used for live inference because its broad offline feature set is incompatible with the live API and its release gate fails.
Results apply only to this generated dataset and do not establish real-flight
performance or airworthiness.

An 85–95% accuracy target is not achieved by the live-compatible model across
the frozen partitions: validation accuracy is 0.671, challenge accuracy is
0.699, and time-forward accuracy is 0.616. A separate controlled temporal
feature experiment reached 0.851 on challenge, but only 0.810 on validation
and 0.748 on time-forward data; its minimum fault recall is below 0.80 on
every required split. These numbers are synthetic benchmarks, and a single
high challenge accuracy does not satisfy the release gate. The research model
must remain blocked until independent data and the unchanged per-fault checks
support promotion.

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
`outputs/live_candidate/`. It is marked `NOT_VALIDATED`, and its scores are
uncalibrated. Runtime inference uses this **live-compatible Dataset v1 candidate** only when `AERION_ENABLE_ML_DIAGNOSTICS=1` and `DIGITAL_TWIN_ML_ALLOW_UNVALIDATED=true` are explicitly set in development. The loader checks the trusted repository path, SHA-256, evaluation sidecar, scikit-learn version, feature order, and class mapping before deserialization. Its prediction is exposed as `assessment.diagnostic_result` with source `ml_research`; the legacy `predicted_fault` remains the independent engineering result. Without a compatible artifact, engineering fallback remains active.

The saved minimum required-fault recalls are 0.021 on validation, 0.119 on challenge, and 0.000 on time-forward. The frozen 0.80 release gate therefore fails. This is an application integration for research demonstration, not a model promotion or a claim of flight performance. See the [implementation report](../PHASE2_IMPLEMENTATION_REPORT.md) for executed verification.

## Dataset v2 and Stage 6

Dataset v2 and the Stage 4–6 artifacts are preserved under `../dataset/dataset_v2/`, `outputs_v2/`, `outputs_stage4/`, and `outputs_stage6/`. Stage 6 Candidate B is **not** the runtime model. The [independent audit](outputs_stage6/stage6_independent_audit.md) found a partition reproduction mismatch and cruise-baseline implementation differences; Candidate B also fails the recall gate. Do not overwrite these artifacts or use challenge/time-forward results for tuning. Read-only dataset validation is documented in the [dataset guide](../dataset/README.md).

## Runtime-simulator scenario benchmark (separate research task)

`runtime_scenario_candidate.py` trains against `backend.app.simulation.build_mission`, the same synthetic generator used by the simulation API. Its ten labels are the simulator's `DegradationScenario` values, including `NONE`, `SENSOR_FREEZE`, and `VIBRATION_ANOMALY`; they are **not** the historical nine dataset fault labels. Before fault onset, each generated row is labeled `NONE`. The feature vector uses the existing live-compatible telemetry plus causal rolling features; mission ID, seed, timestamp, scenario choice, and scenario truth are excluded from inference. A streaming parity test compares all features against the offline matrix.

To reproduce in a fresh local checkout with the pinned Python environment, run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m backend.model_evaluation.runtime_scenario_candidate --protocol severity-v4 --output backend/runtime/scenario_model
```

The command refuses an existing output directory and never touches historical datasets or model artifacts. It creates `evaluation.json` and `research_model.joblib` in the ignored local runtime directory. Two estimators are compared on validation seeds, then the selected model is checked once on challenge seeds. The loader checks the fixed local path, artifact SHA-256, simulator and feature-source hashes, scikit-learn version, ordered feature contract, class mapping, and synthetic gate before deserializing. Do not load joblib files from users or untrusted sources.

The initial 0.8-only protocol selected Extra Trees. Validation accuracy was **0.9582**, macro F1 **0.9603**, and minimum fault recall **0.8186**; challenge accuracy was **0.9648**, macro F1 **0.9680**, and minimum fault recall **0.9071**. The synthetic gate requires every non-`NONE` scenario to reach 0.80 recall on validation and challenge; it passed. These partitions hold out random seeds and mission IDs. The simulator does not model engine-specific physics, so its different engine IDs are not evidence of generalization to real engines. Both splits use the same generator design and fixed 0.8 terminal severity. There is no real telemetry, external dataset, calibrated probability, time-forward audit, or airworthiness validation. This result cannot promote the historical nine-fault model or justify operational use.

A second 0.8-only run with the same pinned environment reproduced the selected estimator, complete validation and challenge metric dictionaries, and serialized model bytes exactly. Both runs wrote only to separate ignored directories under `backend/runtime/`.

For a local backend demonstration, set `AERION_ENABLE_SCENARIO_RESEARCH=true`, restart, save a ten-minute synthetic mission with five-second samples through `POST /api/v1/simulations`, and request `GET /api/v1/simulations/{mission_id}/research-scenario-diagnostics`. This path scores only saved synthetic missions in that evaluated sampling domain and returns an explicit research warning. It is disabled by default and refused in production.

### Severity audit and active local artifact

The first protocol above used only 0.8 terminal severity. A stress check found 0.7863 accuracy and 0.3941 minimum fault recall at severity 0.2. The second protocol trained across 0.2, 0.5, and 0.8 and reached 0.9341 validation and 0.9321 challenge accuracy, but `SENSOR_FREEZE` recall was 0.785 on validation. The third protocol added causal cylinder-one history; its fresh challenge group found 0.781 recall for low-severity combustion instability. The fourth protocol adds a paired-cylinder exhaust-temperature oscillation measure and uses a new challenge seed group (7701 and 7702).

The **active local research artifact** is protocol `severity-v4`. It selected Extra Trees using validation macro F1. Every non-`NONE` scenario exceeds 0.80 recall at **each** severity on validation and challenge:

| Severity | Validation accuracy | Lowest validation fault recall | Challenge accuracy | Lowest challenge fault recall |
| --- | ---: | ---: | ---: | ---: |
| 0.2 | 0.9317 | 0.8620 | 0.9301 | 0.8498 |
| 0.5 | 0.9578 | 0.9340 | 0.9590 | 0.9358 |
| 0.8 | 0.9631 | 0.9514 | 0.9692 | 0.9497 |

Across all three severities, validation accuracy is **0.9508** and macro F1 **0.9533**; challenge accuracy is **0.9528** and macro F1 **0.9546**. The old 0.8-only artifact was backed up locally before activation. Results come from the same simulator design and five-second sampling in every split. The generator has no engine-specific physics; held-out seed IDs are not real-engine generalization. There is no real telemetry, external dataset, calibrated probability, time-forward audit, or airworthiness validation. This synthetic result does not promote the historical nine-fault model or justify operational use.

A post-selection check at the API default 0.65 severity on separate seeds reached 0.9724 accuracy and 0.9462 minimum fault recall. It is an additional synthetic stress check, not a replacement for the frozen validation and challenge partitions.

A clean second `severity-v4` run reproduced the selected estimator, aggregate and per-severity validation/challenge reports, and artifact SHA-256 exactly. The supported saved-mission API path returned 120 scored samples; a one-minute mission was refused with HTTP 503 as outside the evaluated domain.

### Saved `severity-v4` challenge detail

The local `backend/runtime/scenario_model/evaluation.json` records **43,200** challenge rows, accuracy **0.9527778**, and macro F1 **0.9545517**. The table below is transcribed from that artifact. False-negative rate is `1 − recall` for each synthetic class.

| Synthetic class | Precision | Recall | False-negative rate |
| --- | ---: | ---: | ---: |
| ALTERNATOR_DEGRADATION | 1.0000 | 0.9986 | 0.0014 |
| COMBUSTION_INSTABILITY | 0.9081 | 0.9146 | 0.0854 |
| COOLING_DEGRADATION | 0.9584 | 0.9609 | 0.0391 |
| INJECTOR_DEGRADATION | 0.9899 | 0.9612 | 0.0388 |
| LUBRICATION_DEGRADATION | 0.9997 | 0.9589 | 0.0411 |
| MISFIRE | 0.9462 | 0.9314 | 0.0686 |
| NONE | 0.9395 | 0.9546 | 0.0454 |
| SENSOR_DRIFT | 0.8739 | 0.9543 | 0.0457 |
| SENSOR_FREEZE | 0.9800 | 0.9497 | 0.0503 |
| VIBRATION_ANOMALY | 0.9786 | 0.9389 | 0.0611 |

The full 10×10 challenge confusion matrix is under `selected_assessments.challenge.confusion_matrix` in `evaluation.json`. Its rows and columns follow `selected_assessments.challenge.labels` in the class order shown above. The largest fault-to-healthy miss is 177 combustion-instability samples classified as `NONE`; `NONE` is simulator pre-onset or healthy context. The partitions exclude seeds and mission IDs shared with fitting data, and feature selection excludes truth, IDs, timestamps, and severity. All partitions still use the same simulator and preprocessing, so this does not estimate performance on real UAV data. No suitable independent real telemetry is present to validate or approve release.
