# MALE UAV aero-engine digital-twin backend

Run `run_backend.bat` from the repository root, then open
`http://127.0.0.1:8000/docs`.

The service provides validated telemetry ingestion, explainable health/fault
assessment, SQLite history, mission replay, four environmental/mission
simulations, and access to the existing model evaluation report. It is a
software demonstrator based on generated data and is **not flight-certified**.

All non-health API operations now use time-limited bearer authentication and
server-side role authorization. Provision the initial administrator through
environment variables, obtain a token from `POST /api/v1/auth/token`, and use
`Authorization: Bearer <token>`. Configuration, role permissions, limitations,
and production follow-up work are documented in [`SECURITY.md`](SECURITY.md).

The synchronized state is available at `GET /api/v1/engines/{engine_id}/state`
and contains telemetry (with explicit units and quality flags), environment,
physics, performance, health, degradation, fault, mission, and prediction
layers. All configured operating thresholds are labeled **engineering
hypothesis / prototype threshold** and are not manufacturer-approved limits.
The replaceable physics interface and its limitations are documented in
[`app/PHYSICS_MODEL.md`](app/PHYSICS_MODEL.md); its numeric assumptions live in
`app/prototype_physics_assumptions.json`.

Windowed sensor fusion produces thermal, lubrication, combustion, fuel-system,
vibration, electrical, and sensor-health assessments. Each assessment includes
a score, confidence, evidence, reason, severity, and explicit uncertainty.
Fusion assumptions are versioned in `app/sensor_fusion_assumptions.json`.

Hybrid diagnostics explicitly support eleven required fault categories and
combine correlated engineering evidence with past/current statistical features.
The offline classifier is not served because no deployable artifact exists.
Diagnostic outputs therefore use an **uncalibrated engineering score**, never a
fabricated probability, and expose rule/statistical/ML contributions separately.

Telemetry transport is isolated behind adapters selected with
`DIGITAL_TWIN_ADAPTER=SIMULATOR|CAN|SOCKETCAN|FADEC`. The default simulator needs
no hardware. Adapter health is exposed at `GET /api/v1/adapters/health`, and
transport-neutral packets can be submitted to `POST /api/v1/adapters/packets`.
The bundled CAN signal database is generated and makes no ECU/FADEC compatibility
claim. SocketCAN and FADEC remain disconnected unless their transport and an
authorized protocol specification are available.

Mission simulation supports `HIGH_ALTITUDE`, `ENDURANCE`, `HOT_WEATHER`,
`RAPID_THROTTLE`, and `NORMAL_CRUISE`, plus six optional degradation scenarios.
Resolved mission configuration, start time, and random seed are stored for
deterministic replay. Simulated samples use the same `process_telemetry` function
as live ingestion; simulation physics remain explicitly generated.

Stateful replay sessions are created with `POST /api/v1/replays` and support
speed-controlled advance, pause, resume, and deterministic seek. Both stored
simulation missions and historical CSV missions are decoded to the normal
telemetry schema and passed through the same twin processor. Structured
post-flight reports are available at `GET /api/v1/replays/{id}/report` and
`GET /api/v1/missions/{mission_id}/report`.

Run checks with:

```powershell
python -m pytest -q
python -m backend.dataset.validate_dataset
python -m backend.model_evaluation.evaluate_fault_classifier
```
