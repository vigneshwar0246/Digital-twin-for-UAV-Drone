# Runtime simulator scenario mapping

`mission-simulator-v2` produces conceptual live API telemetry. It does **not** generate Dataset v1 or v2 and does not provide training labels for the current classifier. `scenario_truth` records the injected scenario and progression for each generated sample; it is never sent to ML inference as a feature. The first active sample is recorded as `fault_onset_seconds`. Scenario progression starts after 20% of the simulated duration, unlike the historical dataset's separate onset procedure.

| Runtime scenario | Closest historical dataset label | Related engineering diagnostic code | Status |
| --- | --- | --- | --- |
| `NONE` | `Healthy` | none | Prototype checks may still raise findings; no fault detected is not proof of health |
| `MISFIRE` | `Spark_Plug_Misfire` | `MISFIRE` | Conceptual varying RPM and single-cylinder EGT/CHT reduction with vibration; generation methods differ |
| `INJECTOR_DEGRADATION` | `Fuel_Injector_Degradation` | `FUEL_INJECTOR_DEGRADATION` | Conceptual injector effect; generation methods differ |
| `LUBRICATION_DEGRADATION` | `Lubrication_System_Degradation` | `LUBRICATION_ISSUE` | Conceptual oil pressure, temperature, vibration effect |
| `COOLING_DEGRADATION` | `Cooling_System_Degradation` | `COOLING_SYSTEM_DEGRADATION`, `OVERHEATING` | Related conditions, not equivalent labels |
| `VIBRATION_ANOMALY` | `Bearing_Wear` | `ABNORMAL_VIBRATION` | Vibration anomaly does not establish bearing wear |
| `COMBUSTION_INSTABILITY` | `Combustion_Instability` | `COMBUSTION_INSTABILITY` | Conceptual oscillatory effect |
| `SENSOR_DRIFT` | `Sensor_Drift` | `SENSOR_DRIFT` | One biased CHT measurement; physical CHT is unchanged in this scenario |
| `SENSOR_FREEZE` | none | `SENSOR_FAILURE` | One frozen CHT measurement; no matching historical ML class |
| `ALTERNATOR_DEGRADATION` | `Alternator_Degradation` | `BATTERY_ALTERNATOR_ABNORMALITY` | Conceptual voltage effect |

`INJECTION_TIMING_ABNORMALITY` is an engineering rule without a dedicated runtime scenario or historical fault label. Dataset `Bearing_Wear` is narrower than the runtime `VIBRATION_ANOMALY`. Engineering codes and ML classes must remain separate outputs; this table is a semantic guide, not a validation or training-label conversion.

`FULL_MISSION` is a runtime operating profile with start, warm-up, ground, takeoff, climb, cruise, descent, landing, and shutdown phases. The other runtime profiles retain their previous operating conditions. All schedules, coefficients, and fault effects are unvalidated prototype assumptions, not manufacturer limits or flight evidence.
