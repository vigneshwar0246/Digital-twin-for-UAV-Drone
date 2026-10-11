# Synthetic Engine Dataset — Label Specification

**Applies to:** dataset v1 (data/) and dataset v2 (dataset_v2/)
**Date:** 2026-10-10 | Branch: investigation/synthetic-data-v2-design

## 1. Labelling philosophy

Every row carries three independent axes:

| Column | Type | Meaning |
|---|---|---|
| `fault_type` | Categorical (9 values) | Classifier target — what fault is active |
| `fault_severity` | Ordinal (4 values) | Severity grade — how far fault has progressed |
| `anomaly_label` | Binary int | Is the engine in a diagnosable fault state? |

These are correlated within a mission (fault progression is monotone) but represent distinct concepts. `fault_severity` and `anomaly_label` are label-derived and excluded from ML features.

## 2. Fault-type label semantics

### Healthy
- fault_type="Healthy", anomaly_label=0
- fault_severity="None" when progress==0; fault_severity="Low" when 0<progress<0.08 (pre-onset ramp)

### Spark_Plug_Misfire
- Intermittent combustion failure on affected cylinder: EGT/CHT drop in bursts, RPM drops, elevated vibration
- Distinguishing: intermittent (gate-based) pattern, not monotone

### Fuel_Injector_Degradation
- Lean condition: AFR rises, EGT rises strongly (+95*progress), CHT rises moderately (+25*progress)
- Distinguishing: EGT rise >> CHT rise on affected cylinder; fuel flow reduction

### Lubrication_System_Degradation
- Oil temp +25*progress, vibration +3.2*progress, oil pressure drops
- Distinguishing: oil pressure drop + oil temp rise + vibration, no cylinder-specific CHT/EGT

### Cooling_System_Degradation
- Multi-cylinder CHT rise with thermal lag: weights np.roll([1.0,0.88,0.58,0.30], affected_cylinder)
- No EGT change. Small oil temp rise (+7*progress*load/100)
- DISTINGUISHING from Sensor_Drift: MULTIPLE cylinders rise (not single)
- v2: affected_cylinder is independently randomised per mission

### Bearing_Wear
- Vibration +7*progress*(0.4+0.6*rpm/3000), efficiency -9*progress, oil temp +9*progress
- Distinguishing: vibration strongly RPM-proportional

### Combustion_Instability
- Oscillatory AFR, RPM, EGT, vibration (sinusoidal wave, two frequencies)
- Distinguishing: oscillatory not monotone; affects all cylinders

### Sensor_Drift  (SENSOR MALFUNCTION — measurement fault)
- Electronic drift in CHT sensor on affected cylinder: cht[:,cylinder] += 65*progress
- TRUE physical temperature is NOT changed (only the sensor reading is biased)
- No EGT change, no oil change, no multi-cylinder effect
- DISTINGUISHING from Cooling: only ONE cylinder CHT rises, no corresponding EGT or oil signal
- v2: affected_cylinder is independently randomised per mission (NOT hardcoded to cylinder 0)

### Alternator_Degradation
- Voltage drops: alt_v -= 6.5*progress + sinusoidal
- No thermal or mechanical effects

## 3. Severity label semantics

| fault_severity | progress range | anomaly_label | Interpretation |
|---|---|---|---|
| "None" | 0 | 0 | Healthy, no degradation |
| "Low" | 0 < p < 0.34 | 0 or 1 | Early fault: if p<0.08 labeled Healthy; if p>=0.08 diagnosable |
| "Medium" | 0.34 <= p < 0.67 | 1 | Moderate fault |
| "High" | 0.67 <= p <= 1.0 | 1 | Severe fault |

### Healthy rows with fault_severity="Low"
In missions with faults, the pre-onset ramp (0 < progress < 0.08) generates rows where:
- fault_type="Healthy" (not yet diagnosable)
- fault_severity="Low" (early degradation tracking)
- anomaly_label=0
This is intentional. 6,773 such rows exist in v1; v2 preserves this design.

## 4. Fault progression model
onset = uniform(0.30, 0.55) x mission_length
progress[onset:] = linspace(0.03, terminal_value, n-onset) x noise
progress = cumulative_max(clip(progress, 0, 1))  [monotone]
Label switches from Healthy to fault class exactly at progress >= 0.08.

## 5. Ambiguous conditions
Low-severity samples have weak signals. Known overlaps:
- Cooling Low vs Sensor_Drift Low: CHT spread similar; distinguished by multi-cylinder vs single-cylinder pattern
- Injector Low vs Cooling Low: both raise CHT on affected cylinder; distinguished by EGT rise (injector only)
- Bearing vs Lubrication: both raise vibration+oil; distinguished by RPM-dependence and oil pressure

At very low severity with sensor noise, some samples are genuinely ambiguous. This is acknowledged.

## 6. Excluded label-derived columns
fault_type, fault_severity, anomaly_label, health_index, rul_hours, mission_reliability_percent,
mission_outcome, timestamp, mission_id, engine_id, operating_hours, cycle_count

## 7. v2-specific design changes
1. Engine assignment: independent of mission index (pool of 20 engines, randomly assigned)
2. Cylinder assignment: uniform random per fault mission, balanced per fault type
3. Sensor drift: affected_cylinder is randomly assigned (not hardcoded to cyl 0)
4. Same sensor set and physical models as v1
5. Same fault physics, only assignment correlations are removed
