# AERION physics-guided generated datasets

This package creates deterministic telemetry for a generic turbocharged,
four-cylinder, four-stroke aero piston engine used by a conceptual MALE UAV.
Generated data is necessary because representative run-to-failure flight data is
scarce, safety-sensitive, and not supplied with this prototype. This is an
educational simulator, not flight-certified data and not validated against
confidential DRDO or manufacturer data.

Dataset v1 contains 100,000 generated rows across 120 missions and 12 simulated engine IDs. The separately preserved Dataset v2 contains 200,000 rows across 240 missions and 20 simulated engine IDs; both use five-second sampling. The application runtime mission simulator is a **third, separate generator**. Its ten scenario labels are not the nine historical dataset labels, and its 95.28% synthetic classifier result must not be attributed to Dataset v1 or v2. See the [scenario mapping](../app/SCENARIOS.md) and [model evaluation guide](../model_evaluation/README.md).

## Contents

- `data/`: Dataset v1 full, train, validation, and test CSV files. Splits contain complete missions.
- `reports/`: machine-readable validation, summary statistics, and class balance.
- `graphs/`: dataset-quality scores and exploratory/physics-validation plots.
- `config.py`: all assumed limits, labels, sampling, sizes, and reproducibility seed (`26054`).
- `dataset_v2/`: separately preserved 200,000-row Dataset v2 CSVs, mission manifest, reports, and graphs. Its class/label assumptions are documented in `LABEL_SPECIFICATION.md`; its configuration and validator are `config_v2.py` and `validate_dataset_v2.py`.

## Telemetry and units

Identifiers and labels include timestamp (UTC ISO-8601), mission/engine ID,
mission phase, fault type/severity, anomaly flag, outcome, cycle count, and time
(seconds). Operating hours and RUL use hours; altitude uses m; ambient, cylinder
head, exhaust gas, and oil temperatures use °C; pressure uses kPa; airspeed uses
km/h; fuel flow uses L/h; vibration is simulated RMS; voltage uses V; injection
timing uses degrees; load, throttle, humidity, efficiency, health, and reliability
use percent. Air-fuel ratio is dimensionless.

## Missions and faults

Missions progress through engine start, warm-up, takeoff, climb, cruise, optional
endurance cruise and rapid-throttle transition, descent, landing, and shutdown.
Altitude, payload/load, duration, humidity, and temperature vary by mission.

Single faults develop gradually: plug misfire introduces one-cylinder thermal
imbalance, RPM instability and vibration; injector degradation changes mixture,
fuel flow and one-cylinder temperatures; lubrication degradation lowers oil
pressure while raising temperature/vibration; cooling degradation raises CHT;
bearing wear raises vibration and reduces efficiency; combustion instability
oscillates RPM/EGT/vibration; sensor drift offsets one CHT sensor while peers stay
consistent; alternator degradation reduces and destabilizes output voltage.

## Read-only validation

From the repository root:

```powershell
.\.venv\Scripts\python.exe -c "from backend.dataset.validate_dataset import validate; checks,_=validate(False); print(sum(not c['passed'] for c in checks), 'failed v1 checks')"
.\.venv\Scripts\python.exe -c "from backend.dataset.validate_dataset_v2 import validate_v2; checks,_=validate_v2(False); print(sum(not c['passed'] for c in checks), 'failed v2 checks')"
.\.venv\Scripts\python.exe -m pytest backend/dataset/tests -q
```

These calls avoid rewriting saved validation reports and graphs. The generator scripts and validator CLI defaults write output files; use an isolated destination for any new experiment and preserve the historical Dataset v1/v2 artifacts. The [Stage 6 independent audit](../model_evaluation/outputs_stage6/stage6_independent_audit.md) records the currently unresolved partition reproduction issue.

## Limitations

Equations are understandable first-order approximations with inertia and noise,
not CFD, thermodynamic-cycle, hardware-in-the-loop, or certified engine models.
Thresholds are configurable engineering assumptions. Simulated RUL and reliability
are labels for algorithm development, not airworthiness decisions. Only one fault
is introduced per mission in this version. Graph validation scores describe data
quality checks; they are not ML accuracy scores because no model is trained here.
