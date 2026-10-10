# AERION judge demo guide

## Start before the judges arrive

Close old project terminals, then run this once from `D:\aircraft`:

```powershell
.\run_project.bat
```

Open `http://127.0.0.1:5173/twin`. No sign-in is required in local demo mode.
Keep `http://127.0.0.1:8000/docs` open in a second tab as backend evidence.

## Recommended 7-minute walkthrough

### 1. Problem and architecture (45 seconds)

Say: “AERION is a modular digital twin for a MALE-UAV aero-piston engine. A
replaceable telemetry adapter feeds a quality-validation boundary. The accepted
signals enter a physics model, windowed sensor fusion, explainable fault
diagnostics, health/degradation tracking, and an RUL proxy. The same core handles
live data, simulation, and replay.”

Open **System Configuration** and point to the pipeline and dataset facts:
100,000 rows, 120 missions, 12 engines. Then return to **Live Digital Twin**.

### 2. Live dataset telemetry (90 seconds)

The backend automatically replays the most useful section of `MISSION_0110` as
`DATASET_ENGINE_010`. It starts with baseline context and reaches a strong
lubrication-degradation region after roughly 9 seconds.

Point out:

- RPM, CHT, EGT, oil pressure/temperature, fuel flow, vibration, electrical
  voltage, timing, load, altitude, pressure, and humidity;
- the green backend-connected state and changing timestamps;
- engine health, anomaly score, active faults, and RUL;
- the trend chart proving values are changing rather than being static cards.

When the fault appears, say: “The CSV label is not sent into the algorithm. The
twin sees sensor values only. Here low oil pressure and elevated vibration flow
through physics residuals and sensor fusion; the independent diagnostic output
identifies lubrication degradation and generates an evidence-backed inspection
recommendation.”

### 3. Explain the prediction (75 seconds)

Open **AI Diagnostics**. Expand **Contributing evidence**.

Explain that `backend/app/core.py` calculates the synchronized state;
`backend/app/physics.py` estimates expected behavior and residuals;
`backend/app/sensor_fusion.py` combines related channels over a time window;
and `backend/app/diagnostics.py` ranks supported fault hypotheses. This is a
hybrid, explainable prototype. Its scores are engineering/anomaly scores, not
calibrated probabilities.

Open **RUL & Degradation**. Explain that RUL falls as/beause health loss and
cumulative damage rise. It includes wide uncertainty and is explicitly an
engineering proxy until real run-to-failure engine data is available.

### 4. Mission and environmental simulation (90 seconds)

Open **Mission Simulation**, select a scenario, and click **Run backend
simulation**. Demonstrate at least:

- High Altitude;
- Hot Weather;
- Rapid Throttle;
- one degradation case such as Oil Pressure Drop or Abnormal Vibration.

Say: “These missions are deterministic from a stored seed. They pass through
the same processing function as telemetry, so simulation is not a separate fake
dashboard path.”

### 5. Replay and post-flight analysis (60 seconds)

Open **Mission Replay**, click **Load backend missions**, enter `MISSION_0110`,
then **Open mission**. Use Play/Pause and the timeline. Point out fault events.

Open **Reports** to show mission statistics, health before/after, RUL, faults,
maintenance actions, and JSON/CSV/PDF export.

### 6. Scalability and roadmap (45 seconds)

Open **System Configuration** and the architecture graphic. Say: “The simulator,
CAN, SocketCAN, and future FADEC integrations sit behind the adapter interface.
The core is transport-independent. A production path adds authenticated GCS
identity, TLS/mTLS, signed anti-replay telemetry, an edge deployment, fleet
storage, calibrated ML trained on real engine data, and certification evidence.”

## Where each requirement is implemented

| Requirement | Implementation |
|---|---|
| Sensor ingestion | `backend/app/adapters/`, strict `Telemetry` schema |
| Dataset live feed | `feed_demo_dataset()` in `backend/app/main.py` |
| Physics-informed behavior | `backend/app/physics.py` |
| Sensor fusion | `backend/app/sensor_fusion.py` |
| Fault detection | `backend/app/diagnostics.py` and `core.py` |
| Health/degradation/RUL | synchronized `HealthState`, `DegradationState`, `PredictionState` in `core.py` |
| Mission profiles | `backend/app/simulation.py` |
| Historical replay/report | `backend/app/replay.py` |
| Dashboard | `frontend/src/workspace/` |
| Dataset/model evaluation | `backend/dataset/` and `backend/model_evaluation/` |

## Honest answers to likely judge questions

- **Is this flight certified?** No. It is a functional software demonstrator
  using generated data and prototype engineering assumptions.
- **Is the fault label leaked into prediction?** No. The online core receives the
  telemetry schema only. The dataset label is retained only in demo status for
  verification.
- **Is the displayed score a probability?** No. It is an explainable engineering
  anomaly score. Probability calibration needs representative real data.
- **Is RUL validated?** No. It is a bounded engineering proxy showing the
  architecture and degradation response; real run-to-failure validation is the
  next step.
- **Can it use CAN/FADEC?** CAN and SocketCAN adapter boundaries exist. Hardware
  deployment requires the authorized ECU/FADEC signal specification and rig
  validation.
- **Why is this scalable?** Transport, schemas, physics, fusion, diagnostics,
  persistence, replay, and UI are separate modules, so each can be replaced or
  deployed at edge/server layers independently.

## Emergency recovery

If a stale process owns a port, close all previous project terminals and run:

```powershell
Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue |
  Select-Object LocalPort,OwningProcess
```

Stop only the listed old project process IDs, then rerun `run_project.bat`.
