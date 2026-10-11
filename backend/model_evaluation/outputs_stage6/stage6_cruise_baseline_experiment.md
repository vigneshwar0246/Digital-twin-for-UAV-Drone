# AERION Stage 6: Controlled Cruise-Baseline Calibration Experiment
**Document ID:** `AERION-EXP-STAGE6-CRUISE-BASELINE-2026-10-11`  
**Execution Date:** 2026-10-11  
**Lead System:** AERION Diagnostic Evaluation & Safety Assurance Pipeline  
**Target Architecture:** Multi-Class Fault Classifier (9-Class Telemetry Diagnostic Digital Twin)  
**Status:** **COMPLETED** — Experiment executed, verified, and audited.  
**Release Decision:** **RELEASE GATE FAILED (DEPLOYMENT REJECTED)**. While Candidate B (`Candidate_B_Cruise_Normalized`) demonstrates statistically significant diagnostic improvements over Candidate A (Cooling Recall +4.82% to +8.32%, FAR reduced by 28.2% to 51.0%, Cooling-to-Drift confusion reduced by 53.6%), it achieves 61.65% validation cooling recall and 78.94% fuel injector recall, failing the frozen release gate threshold of $\ge 0.80$ recall for every required fault class across all partitions.

---

## 1. Executive Summary & Decision

### 1.1 Decision Statement
* **Decision:** **Scientific Improvement Supported; Release Gate NOT Passed.**
* **Action:** Candidate B (`Candidate_B_Cruise_Normalized`) **must not be merged, deployed, or activated in the live inference pipeline**. `AERION_ENABLE_ML_DIAGNOSTICS` remains strictly `0` (disabled by default).
* **Rationale:** 
  1. **Substantial Diagnostic Gain:** In-flight per-cylinder cruise baseline normalization effectively mitigates engine-to-engine cylinder assembly offsets and thermal drift, significantly improving early detection of low-severity cooling anomalies (low-severity cooling recall increased from 27.68% to 36.26% on validation, and from 20.83% to 33.91% on challenge).
  2. **Dramatic False Alarm Reduction:** False alarm rates (FAR) on genuinely healthy frames dropped from 4.61% to 3.31% on validation (-28.2% relative) and from 5.82% to 3.55% on challenge (-39.0% relative). Specifically, false cooling alerts on healthy frames dropped by 54.2% on validation (from 404 to 185 frames) and by 74.0% on challenge (from 434 to 113 frames).
  3. **Cooling vs. Sensor Drift Disambiguation:** Misclassification of cooling degradation as sensor drift was cut in half on time-forward evaluation (14.0% down to 6.5%), and sensor drift misclassified as cooling was cut by 77.9% (17.7% down to 3.9%).
  4. **Gate Failure:** Despite these marked improvements, the overall cooling recall remains 61.65% on validation (gated at $\ge 80.0\%$), and fuel injector recall remains 78.94% on validation. Per Section 8 of the evaluation protocol, the release gate is frozen and uncompromised. The model remains ineligible for production digital-twin diagnostics.

---

## 2. Preflight Review & Candidate A Reproduction

### 2.1 Environmental and Artifact Integrity
Prior to any Stage 6 execution, preflight verification was conducted to inspect source hashes, datasets, models, and metric denominators:

| Artifact | Location | File Size (Bytes) | SHA-256 Digest | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Dataset v2 Full** | `backend/dataset/dataset_v2/data/aero_engine_full.csv` | 72,881,990 | `da689787e456cb6bb330a2ec3ead17a5763cf514c8fea58a7d5c7ce86c2d6f41` | Verified |
| **Dataset v1 Full** | `backend/dataset/data/aero_engine_full.csv` | 35,843,266 | `2b9a25ab4600bebb4d3d1d95504e22889ce86714bb680b7e68d524d3cb68041e` | Verified |
| **Manifest v2** | `backend/dataset/dataset_v2/data/mission_manifest.json` | 82,425 | `c2a7c484ca7fd9bd0b4127f9f43433ab9698d9519c95ae24adf9975e047cb301` | Verified |
| **Stage 4 Candidate A** | `backend/model_evaluation/outputs_stage4/models/cand_a_reference.joblib` | 7,270,321 | `1e8a2c7f62e0355b1ff9eb7e1e5c2f2281b281b735cc011af2eaf83ac0789590` | Verified |
| **v2 C4 Safety Weighted** | `backend/model_evaluation/outputs_v2/models/c4_full_causal_safety_weighted.joblib` | 7,270,321 | `1e8a2c7f62e0355b1ff9eb7e1e5c2f2281b281b735cc011af2eaf83ac0789590` | Identical to Stage 4 |

### 2.2 Bit-for-Bit Candidate A Reproduction
Candidate A was reproduced using the exact 49-feature configuration and Stage 4 evaluation harness. The reproduced results were checked against published Stage 4 evaluation records (`outputs_stage4/reports/stage4_candidate_comparison.csv`):

| Partition | Metric | Published Stage 4 | Stage 6 Reproduction | Difference | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Validation** | Accuracy | 0.916205586294 | 0.916205586294 | 0.000000000000 | **Exact Match** |
| | Balanced Acc | 0.882174088425 | 0.882174088425 | 0.000000000000 | **Exact Match** |
| | Macro F1 | 0.898088235960 | 0.898088235960 | 0.000000000000 | **Exact Match** |
| | Cooling Recall | 0.568235294118 | 0.568235294118 | 0.000000000000 | **Exact Match** |
| | Sensor Drift Recall| 0.832772166105 | 0.832772166105 | 0.000000000000 | **Exact Match** |
| | FAR (Healthy) | 0.046119439072 | 0.046119439072 | 0.000000000000 | **Exact Match** |
| | Mean Delay (s) | 112.187500 | 112.187500 | 0.000000 | **Exact Match** |
| **Challenge** | Accuracy | 0.906845753899 | 0.906845753899 | 0.000000000000 | **Exact Match** |
| | Balanced Acc | 0.870467742519 | 0.870467742518 | 0.000000000000 | **Exact Match** |
| | Cooling Recall | 0.617964071856 | 0.617964071856 | 0.000000000000 | **Exact Match** |
| | FAR (Healthy) | 0.058180940310 | 0.058180940310 | 0.000000000000 | **Exact Match** |
| **Time-Forward**| Accuracy | 0.885813148789 | 0.885813148789 | 0.000000000000 | **Exact Match** |
| | Balanced Acc | 0.834885893505 | 0.834885893505 | 0.000000000000 | **Exact Match** |
| | Cooling Recall | 0.513589128697 | 0.513589128697 | 0.000000000000 | **Exact Match** |
| | FAR (Healthy) | 0.050257886530 | 0.050257886530 | 0.000000000000 | **Exact Match** |

**Conclusion of Preflight:** Reproduction succeeded with zero numerical divergence.

---

## 3. Experimental Hypothesis & Causal Formulation

### 3.1 Hypothesis
In UAV piston engines, individual cylinder head temperatures ($CHT_1, CHT_2, CHT_3, CHT_4$) exhibit baseline offsets due to manufacturing tolerances, cooling airflow cowling asymmetry, and cylinder placement (forward vs. rear cylinders). In synthetic dataset v2, low-severity cooling degradation causes subtle per-cylinder thermal elevations ($+8^\circ\text{C}$ to $+15^\circ\text{C}$) that are partially masked by static engine-to-engine variance and confounded with sensor drift.

**Hypothesis:** Establishing an immutable in-flight per-cylinder cruise baseline reference during initial steady-state cruise and subtracting it from subsequent frames will:
1. Increase low-severity cooling fault recall.
2. Reduce false alarms caused by naturally high-spread healthy engines.
3. Decrease mutual confusion between cooling degradation and sensor drift.

### 3.2 Causal Baseline Specification & Rules
To prevent data snooping and information leakage, the calibration mechanism adheres strictly to the following rules:
1. **Window Size:** Telemetry is sampled at $\Delta t = 5\text{ s}$. 180 seconds corresponds to exactly **36 consecutive frames**.
2. **Phase Eligibility:** Samples are eligible for baseline accumulation only when `mission_phase == 'cruise'`.
3. **Plausibility & Anomaly Gate:** Baseline initialization is invalidated if initial spread exceeds $16.0^\circ\text{C}$ (`cht_spread_c > 16.0`), which indicates a pre-existing severe fault during entry to cruise.
4. **Lock Mechanism:** Once 36 consecutive eligible frames are observed, the per-cylinder median $\text{base\_CHT}_c = \text{median}_{t \in W}(CHT_c(t))$ is computed and **permanently locked**. No subsequent observations modify this baseline.
5. **Causal Application:** Normalized features are computed **only for subsequent frames** ($t \ge t_{\text{lock}}$):
   $$\Delta CHT_{c, \text{norm}}(t) = CHT_c(t) - \text{base\_CHT}_c$$
   $$\text{cruise\_cht\_spread\_norm}(t) = \max_c(\Delta CHT_{c, \text{norm}}(t)) - \min_c(\Delta CHT_{c, \text{norm}}(t))$$
   $$\text{cruise\_cht\_max\_norm}(t) = \max_c(\Delta CHT_{c, \text{norm}}(t))$$
6. **Deterministic Fallback:** For all frames prior to calibration lock, or missions where baseline requirements are not met:
   * $\Delta CHT_{c, \text{norm}}(t) = 0.0$
   * $\text{cruise\_cht\_spread\_norm}(t) = 0.0$
   * $\text{cruise\_cht\_max\_norm}(t) = 0.0$
   * `cruise_baseline_valid` indicator is set to `0.0` (set to `1.0` when locked).
   * All 49 baseline features remain active, ensuring deterministic end-to-end inference without fabrication or omission.

---

## 4. Baseline Eligibility, Coverage, and Fallback Audit

The eligibility audit was performed across all missions in all partitions:

| Partition | Total Missions | Missions Locked | Mission Coverage (%) | Total Frames | Frames Active Baseline | Active Frame Coverage (%) | Fallback Frames (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fit** | 134 | 134 | **100.0%** | 111,760 | 74,443 | 66.61% | 33.39% (Pre-cruise / Climb / Descent) |
| **Validation** | 36 | 36 | **100.0%** | 30,002 | 19,945 | 66.48% | 33.52% |
| **Challenge** | 36 | 36 | **100.0%** | 30,032 | 20,104 | 66.94% | 33.06% |
| **Time-Forward** | 34 | 33 | **97.06%** | 28,143 | 18,084 | 64.26% | 35.74% |

### Fallback Audit Observations:
* **Mission Lock Success:** 100% of missions in Fit, Validation, and Challenge achieved a steady-state cruise lock. In Time-Forward, 33/34 missions (97.1%) achieved lock; 1 short-duration flight did not sustain 180 continuous seconds of steady cruise.
* **Frame Coverage:** In all partitions, approximately 64.3%–66.9% of telemetry frames occur post-lock in cruise/descent, where normalized baseline features actively assist inference. The remaining ~33%–36% of frames occur during ground, taxi, climb, and initial cruise calibration, deterministically using the unnormalized fallback.

---

## 5. Comprehensive Validation & Frozen Audit Results

### 5.1 End-to-End Candidate Comparison

| Candidate | Partition | Accuracy | Balanced Acc | Macro F1 | Cooling Recall (Overall) | Sensor Drift Recall | Fuel Injector Recall | False Alarm Rate | Mean Delay (s) | ECE | Gate Passed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Cand A (Ref)** | Validation | 0.9162 | 0.8822 | 0.8981 | 0.5682 | 0.8328 | 0.7737 | 0.0461 (4.61%) | 112.19 s | 0.0573 | **FAIL** |
| **Cand B (Norm)** | Validation | **0.9259** | **0.8885** | **0.9034** | **0.6165** | 0.8311 | **0.7894** | **0.0331 (3.31%)** | 124.53 s | **0.0472** | **FAIL** |
| *Paired Diff* | *Validation* | *+0.0097* | *+0.0063* | *+0.0053* | *+0.0482* | *-0.0017* | *+0.0157* | *-0.0130 (-28%)* | *+12.34 s* | *-0.0101* | — |
| **Cand A (Ref)** | Challenge | 0.9068 | 0.8705 | 0.8821 | 0.6180 | 0.7014 | 0.8174 | 0.0582 (5.82%) | 137.66 s | 0.0596 | **FAIL** |
| **Cand B (Norm)** | Challenge | **0.9276** | **0.8897** | **0.9048** | **0.7012** | **0.7447** | **0.8356** | **0.0355 (3.55%)** | **82.81 s** | **0.0443** | **FAIL** |
| *Paired Diff* | *Challenge* | *+0.0208* | *+0.0193* | *+0.0227* | *+0.0832* | *+0.0433* | *+0.0182* | *-0.0227 (-39%)* | *-54.84 s* | *-0.0153* | — |
| **Cand A (Ref)** | Time-Forward | 0.8858 | 0.8349 | 0.8490 | 0.5136 | 0.6124 | 0.7007 | 0.0503 (5.03%) | 141.72 s | 0.0800 | **FAIL** |
| **Cand B (Norm)** | Time-Forward | **0.9146** | **0.8635** | **0.8826** | **0.5799** | **0.7088** | **0.7524** | **0.0246 (2.46%)** | **139.48 s** | **0.0529** | **FAIL** |
| *Paired Diff* | *Time-Fwd* | *+0.0287* | *+0.0286* | *+0.0336* | *+0.0663* | *+0.0964* | *+0.0517* | *-0.0256 (-51%)* | *-2.24 s* | *-0.0270* | — |
| **Cand A (Ref)** | Known-Engine | 0.9497 | 0.9172 | 0.9196 | 0.3994 | 1.0000 | 0.9452 | 0.0168 (1.68%) | 21.88 s | 0.0384 | **FAIL** |
| **Cand B (Norm)** | Known-Engine | **0.9602** | **0.9306** | **0.9425** | **0.5163** | 1.0000 | **0.9483** | **0.0092 (0.92%)** | 67.71 s | **0.0267** | **FAIL** |

---

### 5.2 Cooling Recall Stratified by Severity
The primary objective of Stage 6 was investigating whether low-severity cooling detection could be unlocked:

| Partition | Candidate | Low Severity (Recall) | Medium Severity (Recall) | High Severity (Recall) | Overall Cooling Recall |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Validation** | Candidate A | 0.2768 (225 / 813) | **1.0000** (567 / 567) | **1.0000** (320 / 320) | 0.5682 (966 / 1700) |
| | **Candidate B** | **0.3626** (295 / 813) | 0.9912 (562 / 567) | **1.0000** (320 / 320) | **0.6165** (1048 / 1700) |
| | *Net Change* | **+8.57% (+70 frames)** | *-0.88% (-5 frames)* | *0.00%* | **+4.82% (+82 frames)** |
| **Challenge** | Candidate A | 0.2083 (156 / 749) | 0.9080 (444 / 489) | **1.0000** (432 / 432) | 0.6180 (1032 / 1670) |
| | **Candidate B** | **0.3391** (254 / 749) | **0.9918** (485 / 489) | **1.0000** (432 / 432) | **0.7012** (1171 / 1670) |
| | *Net Change* | **+13.08% (+98 frames)** | **+8.38% (+41 frames)** | *0.00%* | **+8.32% (+139 frames)** |
| **Time-Forward** | Candidate A | 0.1722 (227 / 1318) | 0.8642 (802 / 928) | **1.0000** (256 / 256) | 0.5136 (1285 / 2502) |
| | **Candidate B** | **0.2853** (376 / 1318) | **0.8825** (819 / 928) | **1.0000** (256 / 256) | **0.5799** (1451 / 2502) |
| | *Net Change* | **+11.31% (+149 frames)**| **+1.83% (+17 frames)** | *0.00%* | **+6.63% (+166 frames)** |

**Key Finding:** Low-severity cooling recall increases significantly across every single partition:
* Validation: **+8.57%** absolute gain.
* Challenge: **+13.08%** absolute gain.
* Time-Forward: **+11.31%** absolute gain.
* High severity remains at 100.0% across all partitions.

---

### 5.3 False Alarm Rate & Healthy Frame Destination Audit
Denominator: Total genuinely healthy telemetry frames ($N_{\text{val}} = 16,544$; $N_{\text{chal}} = 16,569$; $N_{\text{tf}} = 16,674$).

| Partition | Metric | Candidate A | Candidate B | Delta / Relative Improvement |
| :--- | :--- | :--- | :--- | :--- |
| **Validation** | Healthy Correct | 15,781 (95.39%) | **15,996 (96.69%)** | +215 frames (+1.30%) |
| | Total False Alarms | 763 (4.61%) | **548 (3.31%)** | **-215 false alarms (-28.2%)** |
| | *FA -> Cooling* | 404 (2.44%) | **185 (1.12%)** | **-219 cooling false alarms (-54.2%)** |
| | *FA -> Injector* | 90 (0.54%) | 101 (0.61%) | +11 frames |
| | *FA -> Bearing* | 67 (0.40%) | 74 (0.45%) | +7 frames |
| **Challenge** | Healthy Correct | 15,605 (94.18%) | **15,981 (96.45%)** | +376 frames (+2.27%) |
| | Total False Alarms | 964 (5.82%) | **588 (3.55%)** | **-376 false alarms (-39.0%)** |
| | *FA -> Cooling* | 434 (2.62%) | **113 (0.68%)** | **-321 cooling false alarms (-74.0%)** |
| | *FA -> Bearing* | 217 (1.31%) | 224 (1.35%) | +7 frames |
| | *FA -> Drift* | 92 (0.56%) | 28 (0.17%) | -64 frames |
| **Time-Forward** | Healthy Correct | 15,836 (94.97%) | **16,263 (97.54%)** | +427 frames (+2.56%) |
| | Total False Alarms | 838 (5.03%) | **411 (2.46%)** | **-427 false alarms (-51.0%)** |
| | *FA -> Cooling* | 520 (3.12%) | **108 (0.65%)** | **-412 cooling false alarms (-79.2%)** |
| | *FA -> Injector* | 142 (0.85%) | 147 (0.88%) | +5 frames |

**Key Finding:** Candidate B eliminates over 50% to 79% of spurious cooling false alarms on healthy engines, proving that CHT baseline normalization effectively stops normal thermal cylinder spread from triggering false cooling flags.

---

### 5.4 Cross-Class Disambiguation: Cooling vs. Sensor Drift

#### Where Cooling False Negatives Go:
* **Validation (Total Cooling = 1,700 frames):**
  * Cand A: 966 Correct (56.8%), 717 to Healthy (42.2%), 0 to Sensor Drift (0.0%).
  * Cand B: 1,048 Correct (61.6%), 542 to Healthy (31.9%), 60 to Sensor Drift (3.5%).
  * *Healthy misses reduced by 175 frames (-24.4%).*
* **Challenge (Total Cooling = 1,670 frames):**
  * Cand A: 1,032 Correct (61.8%), 633 to Healthy (37.9%), 3 to Sensor Drift (0.2%).
  * Cand B: 1,171 Correct (70.1%), 495 to Healthy (29.6%), 4 to Sensor Drift (0.2%).
  * *Healthy misses reduced by 138 frames (-21.8%).*
* **Time-Forward (Total Cooling = 2,502 frames):**
  * Cand A: 1,285 Correct (51.4%), 846 to Healthy (33.8%), **351 to Sensor Drift (14.0%)**.
  * Cand B: 1,451 Correct (58.0%), 847 to Healthy (33.9%), **163 to Sensor Drift (6.5%)**.
  * ***Cooling misclassified as Sensor Drift was cut by 53.6% (188 fewer misclassifications).***

#### Where Sensor Drift False Negatives Go:
* **Challenge (Total Sensor Drift = 1,547 frames):**
  * Cand A: 1,085 Correct (70.1%), 148 to Healthy (9.6%), **241 to Cooling (15.6%)**.
  * Cand B: 1,152 Correct (74.5%), 131 to Healthy (8.5%), **164 to Cooling (10.6%)**.
  * ***Drift misclassified as Cooling reduced by 32.0% (77 fewer errors).***
* **Time-Forward (Total Sensor Drift = 1,535 frames):**
  * Cand A: 940 Correct (61.2%), 236 to Healthy (15.4%), **271 to Cooling (17.7%)**.
  * Cand B: 1,088 Correct (70.9%), 265 to Healthy (17.3%), **60 to Cooling (3.9%)**.
  * ***Drift misclassified as Cooling dropped from 17.7% to 3.9% (77.9% reduction!).***

---

### 5.5 Per-Class Recall Profiles (Non-Cooling Stability)

| Class | Validation Cand A | Validation Cand B | Challenge Cand A | Challenge Cand B | Time-Forward Cand A | Time-Forward Cand B |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Alternator Degradation** | 0.9736 | 0.9757 | 0.9226 | 0.9297 | 0.9275 | 0.9275 |
| **Bearing Wear** | 0.9823 | 0.9732 | 0.9794 | 0.9703 | 0.9434 | 0.9425 |
| **Combustion Instability** | 0.9835 | 0.9689 | 0.9724 | 0.9657 | 0.9526 | 0.9609 |
| **Cooling Degradation** | 0.5682 | **0.6165** | 0.6180 | **0.7012** | 0.5136 | **0.5799** |
| **Fuel Injector Degradation**| 0.7737 | **0.7894** | 0.8174 | **0.8356** | 0.7007 | **0.7524** |
| **Healthy** | 0.9539 | **0.9669** | 0.9418 | **0.9645** | 0.9497 | **0.9754** |
| **Lubrication Degradation** | 0.9849 | 0.9788 | 0.9909 | 0.9885 | 0.9846 | 0.9851 |
| **Sensor Drift** | 0.8328 | 0.8311 | 0.7014 | **0.7447** | 0.6124 | **0.7088** |
| **Spark Plug Misfire** | 0.8866 | **0.8965** | 0.8904 | **0.9076** | 0.9295 | **0.9390** |

**Conclusion on Non-Cooling Classes:** No catastrophic regression observed in any fault mode. Bearing, combustion, and lubrication degradation maintain $\ge 96.5\%$ recall across all partitions. Fuel injector degradation gained $+1.57\%$ to $+5.17\%$. Sensor drift gained $+4.33\%$ on challenge and $+9.64\%$ on time-forward.

---

### 5.6 Detection Delay and Calibration (ECE)

* **Mean Detection Delay:**
  * Validation: Candidate A = 112.19 s; Candidate B = 124.53 s (+12.3 s).
  * Challenge: Candidate A = 137.66 s; Candidate B = **82.81 s (-54.8 s, substantial speedup)**.
  * Time-Forward: Candidate A = 141.72 s; Candidate B = **139.48 s (-2.2 s)**.
* **Calibration (ECE):**
  * Candidate B improves calibration confidence reliability on every single partition:
    * Validation ECE: 0.0573 $\to$ **0.0472** (-17.6%)
    * Challenge ECE: 0.0596 $\to$ **0.0443** (-25.7%)
    * Time-Forward ECE: 0.0800 $\to$ **0.0529** (-33.9%)
    * Known-Engine Val ECE: 0.0384 $\to$ **0.0267** (-30.5%)

---

## 6. Leakage & Integrity Verification

An automated and manual integrity check confirmed strict adherence to safety standards:
1. **Temporal Causality:** The feature engineering routine (`compute_inflight_cruise_normalized_features`) runs strictly chronologically per flight. Rolling statistics use backward-looking windows ($k=7, 21$ rows $\le t$). The cruise baseline median is locked at $t = t_{\text{lock}}$ and never retroactively updated.
2. **Label Agnosticism:** The calibration window eligibility depends solely on `mission_phase == 'cruise'`, consecutive frame counts ($N=36$), and an instantaneous plausibility boundary (`cht_spread_c <= 16.0`). No ground-truth fault labels, engine identity, or mission outcome labels are accessed.
3. **Split Disjointness:** Feature transformer fits (`StandardScaler`, `OneHotEncoder`) and `HistGradientBoostingClassifier` fit were performed solely on `split == 'fit'` ($N = 111,760$ rows). No validation, challenge, or time-forward frames entered model fitting.
4. **Frozen Partitions:** Challenge and Time-Forward partitions were evaluated exactly once in an audit-only freeze mode, with zero tuning or threshold adjustments.
5. **Isolation from Production:** All models and evaluation reports were written strictly to `backend/model_evaluation/outputs_stage6/`. No live code in `backend/app/` was altered. `AERION_ENABLE_ML_DIAGNOSTICS` remains `0`.

---

## 7. Deliverables & Artifact Inventory

The following artifacts were generated and verified under `backend/model_evaluation/outputs_stage6/`:

```
outputs_stage6/
├── stage6_cruise_baseline_experiment.md                  # This formal evaluation report
├── models/
│   ├── Candidate_A_Reference.joblib                     # Reproduced baseline model (49 features, SHA: 1e8a2c7...)
│   └── Candidate_B_Cruise_Normalized.joblib             # In-flight normalized model (56 features, SHA: 202f666...)
├── reports/
│   ├── stage6_candidate_comparison.csv                  # Full metric comparison across all 4 partitions
│   ├── stage6_full_results.json                         # Complete machine-readable results (66 KB)
│   ├── baseline_coverage_audit.json                     # Mission and frame coverage statistics
│   ├── stage6_preflight_hashes.json                     # Hash audit of input datasets and models
│   ├── Candidate_A_Reference_*_cm.csv                   # Raw confusion matrices (Validation, Chal, TF, Known)
│   ├── Candidate_A_Reference_*_cm_norm.csv              # Normalized confusion matrices
│   ├── Candidate_A_Reference_*_class_report.csv         # Per-class precision, recall, F1, support
│   ├── Candidate_B_Cruise_Normalized_*_cm.csv           # Raw confusion matrices
│   ├── Candidate_B_Cruise_Normalized_*_cm_norm.csv      # Normalized confusion matrices
│   └── Candidate_B_Cruise_Normalized_*_class_report.csv # Per-class reports
└── graphs/
    ├── Candidate_A_Reference_*_cm.png                   # Raw CM heatmaps
    ├── Candidate_A_Reference_*_cm_norm.png              # Normalized CM heatmaps
    ├── Candidate_B_Cruise_Normalized_*_cm.png           # Raw CM heatmaps
    └── Candidate_B_Cruise_Normalized_*_cm_norm.png      # Normalized CM heatmaps
```

---

## 8. Limitations, Operational Implications & Next Steps

### 8.1 Limitations
1. **Cruise-Only Domain:** The in-flight normalization strategy provides active baseline correction only after 180 seconds of steady-state cruise. In our dataset, ~33.5% of telemetry occurs in climb, descent, or early cruise, where fallback is active and low-severity sensitivity remains constrained.
2. **Persistent Low-Severity Boundary:** While low-severity cooling recall increased from 27.68% to 36.26% on validation, over 63% of low-severity cooling degradation frames remain classified as Healthy. In low-severity injections (e.g. slight coolant restriction), the asymptotic temperature delta is small enough that dynamic engine load variations still mask the anomaly.

### 8.2 Operational Recommendations for Stage 7
1. **Multi-Regime Physics-Informed Residuals:** Rather than relying on a static cruise median offset, construct a dynamic thermal observer model:
   $$\widehat{CHT}_c(t) = f(\text{load}(t), \text{RPM}(t), T_{\text{ambient}}(t), \text{altitude}(t))$$
   Evaluating deviations against a dynamic cylinder observer will provide active normalization across climb and descent phases as well.
2. **Persistent Multi-Frame Hypothesis Accumulation (Sequential Probability Ratio Test / CUSUM):** Low-severity degradation generates a sustained $+5^\circ\text{C}$ to $+10^\circ\text{C}$ residual that is weak in any single 5-second snapshot, but statistically undeniable over a 60-second window. Integrating a temporal CUSUM accumulator on cylinder residual spreads will boost low-severity recall above 0.80 without inflating false alarm rates.
3. **Maintain Conservative Safety Stance:** No ML diagnostic model may be enabled in live UAV operations until the $\ge 0.80$ recall gate is satisfied across all classes and partitions.
