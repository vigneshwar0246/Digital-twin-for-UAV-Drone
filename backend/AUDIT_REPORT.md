# Digital Twin backend — complete implementation audit

Audit date: 2026-09-11  
Scope: all backend source, APIs, datasets, model reports, tests, configuration,
security, simulation, replay, persistence and adapter code.

## Executive conclusion

**Functional prototype: IMPLEMENTED. Production deployment: NOT READY. Flight,
airworthiness or defence use: NOT VALIDATED AND BLOCKED.**

The backend implements the requested prototype workflows: telemetry ingestion,
a layered digital twin, prototype physics, sensor fusion, eleven fault
categories, history, simulations, deterministic replay, post-flight reports,
hardware-adapter interfaces and role-protected APIs.

This is not a validated aircraft-engine product. All datasets are synthetic.
There are no manufacturer-approved limits/maps, real ECU/FADEC protocol, engine
test-cell or flight results, calibrated fault probabilities, validated RUL
labels, safety assessment, hardware qualification or certification evidence.

| Area | Prototype status | Operational status |
|---|---|---|
| Twin state and ingestion | Substantially complete | Real validation/deployment work blocked |
| Physics and sensor fusion | Prototype complete | Validated maps, limits and uncertainty missing |
| Fault diagnostics | 11 categories implemented | Calibration and real fault evidence missing |
| ML evaluation | Evaluation framework complete | Safety release gate fails |
| Simulation and replay | Prototype complete | Synthetic fidelity not established |
| CAN/SocketCAN/FADEC | Interfaces and synthetic demo complete | Real compatibility unimplemented/unvalidated |
| Authentication/RBAC | Prototype complete | Enterprise controls incomplete |
| Persistence/scalability | Demonstrator complete | SQLite/in-memory state production-blocking |
| Verification | 71 automated tests pass | No HIL, load, security or real-data validation |

No safety-readiness percentage is stated because that would imply evidence that
does not exist.

## Audit labels

- **KEEP**: working code to preserve.
- **IMPROVE**: useful implementation needing stronger engineering.
- **MISSING**: capability not implemented.
- **DANGEROUS/MISLEADING**: safe only when its prototype limitation is visible.
- **PRODUCTION-BLOCKING**: prevents responsible operational deployment.

## Current structure

```text
backend/
├── app/
│   ├── main.py                 API, common processing path, RBAC and audit middleware
│   ├── auth.py / security.py   users, hashing, tokens, roles and rate-limit hook
│   ├── config.py               development/production configuration
│   ├── schemas.py / states.py  telemetry and layered twin models
│   ├── twin.py                 digital-twin synchronization/orchestration
│   ├── physics.py              replaceable prototype physics model
│   ├── sensor_fusion.py        correlated subsystem health
│   ├── diagnostics.py          explainable hybrid fault diagnostics
│   ├── simulation.py           seeded mission simulation
│   ├── replay.py               replay control and post-flight analysis
│   ├── store.py                SQLite persistence
│   ├── thresholds.py           labeled prototype thresholds
│   └── adapters/               Simulator, CAN, SocketCAN, ECU and FADEC interfaces
├── dataset/                    synthetic generation and validation
├── model_evaluation/           splits, metrics, gates, artifacts and reports
├── tests/                      backend automated tests
├── runtime/                    demonstrator database
├── SECURITY.md
└── README.md
```

## API and role audit

| API | Purpose | Access |
|---|---|---|
| `GET /api/v1/health` | Health and non-certified status | Public |
| `POST /api/v1/auth/token` | Expiring bearer token | Public, rate-limited |
| `POST /api/v1/auth/users` | Create users | ADMIN |
| `GET /api/v1/auth/audit` | Request audit records | ADMIN |
| `POST /api/v1/telemetry`, `/batch` | Common telemetry pipeline | ADMIN, OPERATOR |
| `GET /api/v1/engines/{id}/latest|history|state` | Twin reads | All roles |
| simulation create/replay | Generate and replay scenario | ADMIN, OPERATOR, ANALYST |
| simulation configuration | Stored profile and seed | All roles |
| mission list/replay/report | Historical mission access | All roles |
| replay create/control | Session, pause/resume/seek/advance | ADMIN, OPERATOR, ANALYST |
| replay status/report | State and post-flight report | All roles |
| `GET /api/v1/model/report` | Metrics and release gate | ADMIN, ANALYST, MAINTENANCE_ENGINEER |
| `GET /api/v1/adapters/health` | Adapter health/counters | ADMIN, OPERATOR, MAINTENANCE_ENGINEER |
| `POST /api/v1/adapters/packets` | Adapter packet ingestion | ADMIN, OPERATOR |

## Component-by-component findings

### Telemetry — KEEP / IMPROVE

Implemented timestamped engine/mission identity; RPM, throttle, CHT, EGT, oil,
fuel, vibration, electrical, injection timing and environment signals; explicit
units and ranges; quality flags `VALID`, `MISSING`, `STALE`, `OUT_OF_RANGE`,
`SENSOR_FAULT`, `SUSPECT`. Invalid signals are not treated as valid.

Remaining: reconcile with the real sensor/ECU dictionary; validate resolution,
sample rates, latency, clock domains, calibration and missing-data policy; add a
formal producer schema migration/compatibility policy.

### Digital Twin Core — KEEP / IMPROVE

Implemented `TelemetryState`, `EnvironmentState`, `PhysicsState`,
`PerformanceState`, `HealthState`, `DegradationState`, `FaultState`,
`MissionState`, `PredictionState` and aggregate `EngineState`. Each update
validates, synchronizes, derives physics/health, updates degradation, diagnoses,
updates the RUL proxy, explains alerts and persists history.

Remaining: durable distributed state, concurrency/version control, robust
restart recovery, schema migration, fleet partitioning and high-rate testing.

### Physics model — KEEP AS PROTOTYPE / DANGEROUS IF UNQUALIFIED

Separate replaceable interfaces calculate density/load proxies, thermal stress,
lubrication, combustion, vibration, electrical and overall health from engine
and environment signals. Assumptions are documented; deterministic and
monotonic tests exist. Every threshold is labeled **engineering hypothesis /
prototype threshold**.

Production-blocking: replace equations with manufacturer/test-derived maps and
validate envelopes, uncertainty, transient heat/cooling, altitude correction
and calibration using test-cell and flight measurements.

### Sensor fusion and diagnostics — KEEP / IMPROVE

Thermal, lubrication, combustion, fuel, vibration, electrical and sensor health
combine correlated and temporal evidence and expose score, confidence, reason,
severity and uncertainty. Diagnostics cover Misfire, Injector Degradation,
Cooling Degradation, Lubrication Issue, Sensor Drift, Sensor Failure,
Combustion Instability, Overheating, Abnormal Vibration, Electrical Abnormality
and Injection Timing Abnormality. Faults include code/name, severity,
engineering score, impact, evidence, subsystems, action and detection times.

Remaining: these are engineering scores, not calibrated probabilities. Obtain
real fault signatures; validate baselines/windows, noise/covariance, persistence,
hysteresis, false alarms, root-cause ambiguity and approved maintenance actions.

### Degradation and RUL — DANGEROUS / PRODUCTION-BLOCKING

Degradation trends and an explicitly labeled engineering RUL proxy exist for
pipeline/UI development. There is no validated RUL estimator. Required work:
real run-to-failure/censored data, component targets, maintenance resets,
confidence intervals, survival/prognostic validation and error bounds. Never
present the proxy as actual remaining service time.

### ML evaluation — KEEP / MODEL NOT RELEASE READY

Implemented engine-disjoint validation/challenge splits, a mission-disjoint
time-forward audit, unseen-engine/unseen-profile challenge set, class reports,
per-class precision/recall/F1, macro F1, balanced accuracy, confusion matrices,
ECE/calibration, PR curves, false-positive/negative analysis, metadata, split
manifests and leakage tests.

| Split | Accuracy | Balanced accuracy | Macro F1 | ECE |
|---|---:|---:|---:|---:|
| Time-forward | 0.7673 | 0.6209 | 0.6321 | 0.1442 |
| Engine-disjoint validation | 0.8022 | 0.6621 | 0.6482 | 0.1163 |
| Unseen-engine challenge | 0.8406 | 0.7461 | 0.7506 | 0.0809 |

Current output is `MODEL_STATUS=NOT_VALIDATED` and
`RELEASE_READINESS=NOT_RELEASE_READY`. The safety gate fails. Historical weak
test recalls—Cooling 0.4017, Injector 0.7196, Sensor Drift 0.6839—remain warning
evidence, not current readiness claims. Do not manipulate thresholds or the
synthetic dataset merely to pass the gate.

### Simulation — KEEP AS SYNTHETIC DEMONSTRATOR

`HIGH_ALTITUDE`, `ENDURANCE`, `HOT_WEATHER`, `RAPID_THROTTLE` and
`NORMAL_CRUISE` profiles generate all required signals. Cooling, injector,
lubrication, sensor drift, combustion and vibration degradation scenarios exist.
Seeds/configurations are stored and samples use the live ingestion/twin path.

Remaining: validate mission/transient physics and injected signatures against
approved models and measurements. Simulation success does not prove real fault
detection performance.

### Replay/post-flight — KEEP / IMPROVE

Deterministic sessions support engine/mission/time selection, speed, pause,
resume, seek and advance. They recalculate health, anomalies, faults,
degradation, RUL proxy, alerts and environment using an isolated twin and the
same processor. Reports include extrema, fuel use, abnormal duration, fault
events, trends and prototype recommendations.

Remaining: streaming at mission scale, durable/multi-worker sessions, formal
version determinism, signed provenance and approved maintenance wording.

### CAN/SocketCAN/ECU/FADEC — ARCHITECTURE KEEP / REAL INTEGRATION MISSING

Interfaces exist for every requested adapter, with configuration modes,
transport-neutral packets, sequence/duplicate/missing/stale/timestamp checks,
buffering, invalid-frame handling, counters, configurable synthetic CAN mapping
and a simulated CAN stream.

Missing: authorized DBC/protocol, qualified physical interface, ECU/FADEC
handshake, real clock synchronization and recovery, bus-load analysis,
cybersecurity and HIL tests. No real ECU/FADEC compatibility claim is allowed.

### Persistence/scalability — IMPROVE / PRODUCTION-BLOCKING

SQLite persists assessments, simulation configuration, users and audit events
using parameterized queries and indexes. Missing: managed relational/time-series
storage, migrations, retention/partitioning, pooling, encryption, replication,
HA, backup/restore, immutable audit and data governance. In-memory twin/replay
state prevents reliable horizontal scaling.

### Authentication/security — KEEP AS PROTOTYPE / IMPROVE

Implemented salted PBKDF2-HMAC-SHA256 hashes, expiring signed bearer tokens,
five roles, route checks, production-secret validation, request IDs, audit
events and rate-limit hooks. Plaintext passwords are not stored.

Production-blocking: IdP, MFA, account disable/reset administration, token
revocation/refresh, key rotation/secrets manager, certificate/mTLS auth,
hardware-backed keys, telemetry signing/anti-replay, enforced TLS, distributed
rate limiting, immutable SIEM audit, penetration testing and fleet RBAC. See
`SECURITY.md`. This implementation is not defence-certified.

### Logging/error handling/configuration — IMPROVE

Request IDs, request audits, schema errors, bounded inputs, environment-driven
settings, development/production mode, OpenAPI, narrow local CORS and the
Windows launcher exist. Missing: structured logs, metrics/traces/alerts,
dependency checks, redaction policy, SLOs, retry/dead-letter strategy,
environment-specific trusted hosts/CORS, dependency lock/SBOM, containers,
CI/CD, rollback/runbooks and safe behavior when the audit database fails.

### Tests — KEEP / EXPAND

`python -m pytest -q` passes **71 tests**, covering dataset/leakage rules, API
compatibility, state transitions, invalid telemetry, physics, fusion,
diagnostics, adapters, simulation, replay, password storage, token expiry and
signature checks, RBAC denial, request IDs, audit attribution and limiting.

Missing: coverage gate, property/fuzz, migration/failure, race/concurrency,
sustained load, multi-worker, large replay, hardware/HIL, security/penetration,
chaos/recovery and independent real-data acceptance tests.

## All 37 requirements mapped

| # | Requirement | Current status | Remaining work |
|---:|---|---|---|
| 1 | Real-time ingestion | IMPROVE: single/batch/adapter common path | Broker, backpressure, load and live-source validation |
| 2 | Virtual engine state | KEEP: layered synchronized state | Durable distributed recovery |
| 3 | Health monitoring | KEEP prototype | Real calibration/acceptance limits |
| 4 | RPM | KEEP | Sensor/sample-rate validation |
| 5 | CHT | KEEP | Manufacturer limits/calibration |
| 6 | EGT | KEEP | Manufacturer limits/calibration |
| 7 | Oil pressure/temperature | KEEP | Approved lubrication envelope |
| 8 | Fuel flow | KEEP | Calibrated fuel-system model |
| 9 | Vibration | IMPROVE: window features | Spectral/order tracking and validation |
| 10 | Battery/alternator | KEEP prototype | Real electrical specification |
| 11 | Injection timing | KEEP prototype | ECU-authoritative definition |
| 12 | Anomaly detection | KEEP prototype | Real baseline and false-alarm calibration |
| 13 | Misfire | IMPROVE | Real labeled validation |
| 14 | Injector degradation | IMPROVE | Real degradation validation |
| 15 | Cooling degradation | IMPROVE | Validated cooling dynamics |
| 16 | Lubrication issues | IMPROVE | Validated failure signatures |
| 17 | Sensor drift/failure | IMPROVE | Redundancy and real error models |
| 18 | Combustion instability | IMPROVE | Real combustion evidence |
| 19 | Overheating trends | IMPROVE | Approved limits/recovery model |
| 20 | Abnormal vibration | IMPROVE | Frequency/HIL validation |
| 21 | Degradation tracking | KEEP prototype | Component-specific models |
| 22 | RUL | DANGEROUS/BLOCKED: proxy only | Run-to-failure prognostics/uncertainty |
| 23 | Predictive maintenance | IMPROVE | Approved policy/outcome validation |
| 24 | Mission simulation | KEEP prototype | Fidelity validation |
| 25 | High altitude | KEEP prototype | Validated altitude map |
| 26 | Endurance | KEEP prototype | Long-duration validation |
| 27 | Hot weather | KEEP prototype | Validated thermal envelope |
| 28 | Rapid throttle | KEEP prototype | Validated transient model |
| 29 | Historical replay | KEEP | Scale, provenance, durable sessions |
| 30 | Post-flight analysis | KEEP prototype | Approved analysis criteria |
| 31 | Mission reports | KEEP | Signed/exportable/versioned reports |
| 32 | Physics-informed twin | KEEP prototype | Validated maps/uncertainty |
| 33 | Explainable AI | KEEP prototype | Human-factors/calibrated explanations |
| 34 | CAN/SocketCAN-ready | KEEP architecture | Real protocol/hardware validation |
| 35 | ECU/FADEC-ready | IMPROVE architecture | Authorized protocol/integration |
| 36 | Secure telemetry | MISSING/BLOCKED | TLS/mTLS, signing, device identity, anti-replay |
| 37 | Fleet scalability | MISSING/BLOCKED | Distributed store/broker, tenancy, HA, fleet RBAC |

## Highest-priority problems

1. Synthetic-only evidence; no test-cell or flight validation.
2. Classifier safety gate fails and must remain `NOT_RELEASE_READY`.
3. RUL is only an engineering proxy.
4. Physics/thresholds are not manufacturer-approved.
5. No demonstrated real ECU/FADEC compatibility.
6. SQLite and in-memory state block production resilience/scale.
7. Secure device telemetry, signing, TLS/mTLS and key management are absent.
8. Enterprise IAM/MFA/revocation and immutable audit are absent.
9. No HIL, safety/cybersecurity qualification or certification evidence.

## Remaining implementation roadmap

### Phase 1 — demonstrator hardening

- Add database/schema migrations, structured observability and coverage gates.
- Add concurrency, recovery, property, fuzz and load tests.
- Add account disable/reset, token revocation and key-rotation support.
- Lock dependencies, produce an SBOM and add CI security/release checks.

### Phase 2 — integration and scalable platform

- Obtain the authorized ECU/FADEC/CAN specification and implement a real map.
- Add TLS/mTLS, device identity, telemetry signatures and anti-replay storage.
- Replace SQLite/in-memory coordination with production databases, a telemetry
  broker, shared cache/rate limiter, durable jobs and fleet tenancy.

### Phase 3 — engineering validation

- Obtain approved limits/maps, sensor specifications and calibration records.
- Collect governed data from distinct engines: test-cell, flight and run-to-failure.
- Establish ground truth, provenance, operating envelopes and fault taxonomy.
- Calibrate models/uncertainty and rerun engine/mission/time-disjoint evaluations.
- Pass defined hazard-specific recall, precision, false-alarm and calibration gates.

### Phase 4 — assurance

- Perform FMEA/FMECA, hazard analysis and requirements traceability.
- Conduct HIL, environmental, endurance, failure-injection and recovery tests.
- Complete threat modelling and independent penetration testing.
- Validate maintenance outputs and obtain all applicable organizational,
  aviation and defence reviews before any operational claim.

## Reproduction

```powershell
python -m pytest -q
python -m backend.dataset.validate_dataset
python -m backend.model_evaluation.evaluate_fault_classifier
run_backend.bat
```

The evaluator should return a non-release result while the gate fails. That is
correct behavior and must not be suppressed.
