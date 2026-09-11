# SIH26054 physics-guided synthetic dataset

This package creates deterministic telemetry for a generic turbocharged,
four-cylinder, four-stroke aero piston engine used by a conceptual MALE UAV.
Synthetic data is necessary because representative run-to-failure flight data is
scarce, safety-sensitive, and not supplied with this prototype. This is an
educational simulator, not flight-certified data and not validated against
confidential DRDO or manufacturer data.

## Contents

- `data/`: full, train, validation, and test CSV files. Splits contain complete missions.
- `reports/`: machine-readable validation, summary statistics, and class balance.
- `graphs/`: dataset-quality scores and exploratory/physics-validation plots.
- `config.py`: all assumed limits, labels, sampling, sizes, and reproducibility seed (`26054`).

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

## Commands

From the repository root:

```powershell
python -m backend.dataset.generate_dataset
python -m backend.dataset.validate_dataset
python -m pytest backend/dataset/tests -v
```

For a fast custom run: `python -m backend.dataset.generate_dataset --rows 5000 --missions 18 --seed 26054`.

## Limitations

Equations are understandable first-order approximations with inertia and noise,
not CFD, thermodynamic-cycle, hardware-in-the-loop, or certified engine models.
Thresholds are configurable engineering assumptions. Simulated RUL and reliability
are labels for algorithm development, not airworthiness decisions. Only one fault
is introduced per mission in this version. Graph validation scores describe data
quality checks; they are not ML accuracy scores because no model is trained here.
