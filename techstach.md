# AERION / AERO-TWIN — Complete Technology Stack and Implementation Guide

> This document describes what is actually implemented in this repository. The project is an engineering demonstrator built around synthetic data. It is **not flight-certified**, does not use manufacturer-approved limits or engine maps, and must not be used for operational or airworthiness decisions.

## 1. What the project is

AERION is a full-stack digital-twin prototype for the aero-piston engine of a conceptual medium-altitude, long-endurance (MALE) UAV. It combines:

- a cinematic, scroll-driven 3D aircraft introduction;
- an engineering dashboard for telemetry, health, faults, simulation, and replay;
- a FastAPI service that validates and synchronizes engine telemetry;
- a replaceable, first-order prototype physics model;
- windowed sensor-fusion and explainable hybrid diagnostics;
- SQLite telemetry, authentication, and audit storage;
- a deterministic synthetic aero-engine dataset generator; and
- an offline scikit-learn fault-classification experiment.

The most important distinction is that the live application does **not** serve the saved ML classifier. Live diagnostic results come from engineering rules plus statistical history features. The offline classifier is an evaluated candidate whose release gate failed and is explicitly marked not for production.

## 2. High-level architecture

```text
Synthetic dataset / API telemetry / adapter packet
                    |
                    v
        Pydantic schema + quality checks
        (range, missing, stale, sensor fault,
         peer disagreement, sequence/order checks)
                    |
                    v
          Prototype physics model
                    |
                    v
       Windowed subsystem sensor fusion
                    |
                    v
   Explainable rules + robust statistics diagnostics
                    |
                    v
     Unified digital-twin engine state + assessment
                    |
          +---------+----------+
          |                    |
          v                    v
   SQLite persistence      FastAPI JSON API
                               |
                               v
                  React/TypeScript workspace
                  + Three.js visualization
```

The same central telemetry-processing path is reused by direct ingestion, batch ingestion, simulations, adapter packets, and replay. This avoids implementing a separate diagnostic path for demonstrations.

## 3. Technology stack

### Frontend

| Technology | Version in project | Purpose |
|---|---:|---|
| React | 19.1.1 | Component-based UI |
| React DOM | 19.1.1 | Browser rendering |
| TypeScript | ^7.0.2 | Typed engineering workspace files (`.ts`/`.tsx`) |
| JavaScript/JSX | ES modules | Cinematic experience and Three.js components |
| Vite | 7.1.7 | Development server and production bundling |
| `@vitejs/plugin-react` | 5.0.3 | React integration and JSX transformation |
| Three.js | 0.180.0 | WebGL 3D aircraft/engine scene |
| React Three Fiber | 9.3.0 | Declarative React renderer for Three.js |
| Drei | 10.7.6 | Three.js helpers, environment, and lighting |
| GSAP | 3.13.0 | Scroll-linked animation timelines |
| Lenis | 1.3.11 | Smooth scrolling |
| CSS | Native | Responsive visual system, layout, animation, HUD, and dashboard styling |
| Browser History API | Native | Lightweight client-side navigation without a router package |
| Fetch API / WebSocket | Native | Backend polling, API calls, and optional live stream connection |

There is no imported aircraft GLB/GLTF in the current repository. The aircraft, engine, propellers, lighting, atmosphere, and clouds are procedural concept geometry/effects. Replacement guidance is in `frontend/public/models/README.md`.

### Backend and data science

| Technology | Declared range | Purpose |
|---|---:|---|
| Python | project venv; Python 3.12/3.13 artifacts are present | Backend, simulation, dataset, and ML evaluation |
| FastAPI | >=0.115,<1 | REST API, dependency-based authorization, validation integration, OpenAPI docs |
| Uvicorn | >=0.30,<1 | ASGI development server |
| Pydantic | >=2.8,<3 | Strict request, response, state, adapter, and telemetry schemas |
| SQLite (`sqlite3`) | Python standard library | Telemetry/history, users, and audit events |
| pandas | >=2.2,<3 | CSV generation, feature engineering, splits, reports |
| NumPy | >=2.0,<3 | Numerical simulation and feature calculations |
| scikit-learn | >=1.5,<2 | Offline preprocessing, model training, predictions, and metrics |
| Matplotlib | >=3.9,<4 | Evaluation and dataset graphs |
| joblib | installed through scikit-learn dependency | Candidate model serialization |
| pytest | >=8,<10 | Backend, dataset, model protocol, security, and integration tests |
| HTTPX | >=0.27,<1 | FastAPI/API testing support |

### Testing and tooling

- Node's built-in test runner executes frontend unit/experience tests.
- Playwright 1.55.0 performs end-to-end browser tests and responsive checks.
- FastAPI automatically exposes Swagger/OpenAPI documentation at `/docs`.
- PowerShell and batch launchers create the virtual environment, install dependencies, launch both services, and shut down the backend with the frontend.
- npm uses the committed `package-lock.json` for repeatable frontend dependency resolution.

## 4. Models used

“Model” means several different things in this project; they should not be conflated.

### 4.1 Live prototype physics model

Implementation: `backend/app/physics.py` (`PrototypePhysicsModel`).

Interface: `PhysicsModel.evaluate(PhysicsInput) -> PhysicsResult`. This protocol is the replacement boundary for a future engine map, cycle model, system-identification model, or approved external service.

It calculates explainable relative proxies for:

- air density from pressure/temperature/humidity, with an altitude fallback;
- engine load from reported load and density-corrected throttle;
- expected fuel flow from normalized RPM and load;
- expected injection timing from load and altitude;
- mean CHT, mean EGT, and cylinder spread;
- thermal stress;
- lubrication, combustion, vibration, and electrical health;
- efficiency; and
- overall health.

All coefficients come from `backend/app/prototype_physics_assumptions.json`. These are explicitly synthetic engineering assumptions, not thermodynamic-cycle simulation, CFD, a manufacturer performance map, or approved control logic.

### 4.2 Live sensor-fusion model

Implementation: `backend/app/sensor_fusion.py` (`SensorFusionEngine`).

This is a deterministic, windowed engineering algorithm rather than a learned neural network. It combines related signals into seven subsystem assessments:

1. thermal health;
2. lubrication health;
3. combustion health;
4. fuel-system health;
5. vibration health;
6. electrical health; and
7. sensor health.

Every result exposes a health score, confidence, evidence signals, reason, severity, and uncertainty. Confidence accounts for signal availability and, where relevant, whether a temporal window contains enough samples. Assumptions are versioned in `backend/app/sensor_fusion_assumptions.json`.

Examples include contextualizing CHT/EGT against ambient temperature and load, checking oil pressure only in running conditions, comparing fuel/timing residuals, evaluating rolling vibration mean and variability, and reducing sensor health when quality flags or peer disagreement are present.

### 4.3 Live hybrid diagnostic model

Implementation: `backend/app/diagnostics.py` (`HybridDiagnosticEngine`).

It combines two active evidence sources:

- correlated engineering-rule evidence; and
- causal statistical anomalies derived only from previous/current samples in the same mission, using a robust median/MAD-style z-score.

It has an interface for a future `MLDiagnosticProvider`, but no provider is connected. The output therefore reports `probability: null`, labels its result an **uncalibrated engineering score**, and exposes rule, statistical, and ML contributions separately.

The eleven live diagnostic categories are:

1. Misfire
2. Fuel Injector Degradation
3. Cooling System Degradation
4. Lubrication Issue
5. Sensor Drift
6. Sensor Failure
7. Combustion Instability
8. Overheating
9. Abnormal Vibration
10. Battery/Alternator Abnormality
11. Injection Timing Abnormality

Each activated diagnosis includes severity, engineering score, health impact, evidence, affected subsystems, recommended action, first/last detection times, algorithm version, and uncertainty. Numeric assumptions are stored in `backend/app/diagnostic_assumptions.json`.

### 4.4 Health, degradation, anomaly, and RUL estimates

`DigitalTwinCore` assembles telemetry, physics, fusion, and diagnostic results into a synchronized state. The state has telemetry, environment, physics, performance, health, degradation, fault, mission, and prediction layers.

The overall health index and remaining-useful-life output are engineering proxies. RUL is derived from the prototype health/degradation behavior; it is not a validated survival model, fleet-trained prognostic model, or failure probability. The UI deliberately labels anomaly values as engineering scores and RUL as a proxy.

### 4.5 Offline machine-learning classifier

Implementation: `backend/model_evaluation/evaluate_fault_classifier.py`.

| Item | Implementation |
|---|---|
| Algorithm | `HistGradientBoostingClassifier` |
| Model version | `hgb-fault-candidate-v2.0.0` |
| Iterations | 220 |
| Learning rate | 0.075 |
| Maximum leaf nodes | 31 |
| L2 regularization | 0.5 |
| Reproducibility seed | 26054 |
| Numeric preprocessing | `StandardScaler` |
| Categorical preprocessing | `OneHotEncoder(handle_unknown="ignore")` for mission phase |
| Pipeline | scikit-learn `ColumnTransformer` + `Pipeline` |
| Class balancing | inverse-frequency sample weights |
| Extra safety cost | cooling degradation 5.0; sensor drift 1.6 |
| Artifact | `backend/model_evaluation/outputs/fault_classifier_candidate.joblib` |

The trained classes are Healthy plus eight simulated fault types: alternator degradation, bearing wear, combustion instability, cooling-system degradation, fuel-injector degradation, lubrication-system degradation, sensor drift, and spark-plug misfire.

Features include current telemetry, mission phase, cylinder mean/spread features, cooling residuals, current-to-previous deltas, 7/21-sample rolling standard deviations, 21-sample rolling means, CHT rise rate, and thermal-response residuals. Temporal features reset at mission boundaries and use only current/past samples.

Potential leakage fields are excluded: timestamp, engine/mission identity, operating hours, cycle count, fault/severity labels, anomaly label, health, RUL, reliability, outcome, and mission-profile identity.

Evaluation uses mission-disjoint partitions, engine-disjoint validation/challenge groups, and a separate time-forward audit on fitting-engine identities. It generates classification reports, raw/normalized confusion matrices, precision-recall curves, calibration measures, false-positive/negative analyses, per-class recall/F1 graphs, a split manifest, and a dataset hash.

The recorded challenge/test result is approximately 84.06% accuracy, 74.61% balanced accuracy, and 75.06% macro F1. Those aggregate numbers are not sufficient for release: several important fault classes miss the required 0.80 recall on one or more required splits. Probabilities are also uncalibrated. Consequently:

- `model_status`: `NOT_VALIDATED`
- `release_readiness`: `NOT_RELEASE_READY`
- release gate: failed
- live serving: disabled

### 4.6 AI/LLM and external models

No LLM, generative-AI API, computer-vision model, hosted foundation model, OpenAI model, or third-party inference service is used by the application. No external 3D or image service is required at runtime.

## 5. Synthetic dataset

The dataset package lives in `backend/dataset/`. It creates deterministic, physics-guided telemetry because representative real run-to-failure flight data was not supplied.

Current generated dataset summary:

- 100,000 rows and 40 columns;
- 120 complete missions;
- 12 engine identities;
- approximately 138.72 mission hours;
- deterministic seed `26054`;
- zero missing values and zero duplicate rows in the generated full dataset; and
- full, train, validation, test, and challenge CSV files.

Mission phases cover engine start, warm-up, takeoff, climb, cruise, optional endurance/rapid-throttle behavior, descent, landing, and shutdown. Environment, altitude, payload/load, humidity, temperature, and duration vary by mission.

The generator gradually injects one fault per affected mission. Simulated effects include cylinder thermal imbalance, RPM instability, mixture/fuel-flow changes, oil-pressure loss, temperature rise, vibration, sensor offsets, and alternator voltage degradation. The simulator uses first-order relationships, inertia, and seeded noise—not real engine test-cell data.

Dataset validation checks schema, bounds, mission split isolation, reproducibility, class balance, physical trends/correlations, and label behavior. Reports and visualizations are written under `backend/dataset/reports` and `backend/dataset/graphs`.

## 6. Backend implementation

### Telemetry processing

The central `DigitalTwinCore` keeps per-engine state and bounded history under thread locks. Incoming telemetry is checked for:

- required fields and Pydantic types;
- finite numeric values;
- configured plausibility ranges;
- timestamp progression/staleness;
- missing and failed sensors; and
- cylinder-peer disagreement and suspect measurements.

Rejected/suspect signals are not silently treated as valid. Parameter state carries value, unit, quality, and reason. Stale telemetry does not replace the latest synchronized state.

### Transport adapters

`DIGITAL_TWIN_ADAPTER` selects `SIMULATOR`, `CAN`, `SOCKETCAN`, or `FADEC`.

- Simulator is the default and requires no hardware.
- CAN decodes the bundled synthetic signal mapping.
- SocketCAN adds a configured Linux CAN channel such as `can0` but remains disconnected without transport support.
- FADEC is a protocol placeholder and will not claim compatibility without an authorized specification.

The transport-neutral packet layer validates timezone-aware timestamps, source, engine/mission IDs, sequence numbers, signal quality, protocol metadata, and clock metadata. It detects duplicates, stale/future packets, sequence gaps, invalid frames, and loss; buffers out-of-order packets and releases them after recovery or timeout. Adapter health counters are exposed by API.

### Mission simulation and replay

Simulation supports `HIGH_ALTITUDE`, `ENDURANCE`, `HOT_WEATHER`, `RAPID_THROTTLE`, and `NORMAL_CRUISE`, plus optional degradation scenarios. A resolved configuration, seed, and start time are stored so a simulation can be reproduced. Generated samples pass through the same `process_telemetry` path as external telemetry.

Replay sessions can load a stored simulated mission or historical CSV mission, then pause, resume, seek by virtual time, advance at a selected speed, and generate a post-flight report. Each replay uses isolated volatile twin state so old rolling windows do not contaminate its assessment.

### Persistence

SQLite is used without an ORM. The application stores telemetry/history and simulation metadata, while the authentication repository stores users and audit events. The combined local launcher uses `backend/runtime/local-development.db`.

### API surface

Main API prefix: `/api/v1`.

| Area | Representative endpoints |
|---|---|
| Health/demo | `GET /health`, `GET /demo/status` |
| Authentication | `POST /auth/token`, `POST /auth/users`, `GET /auth/audit` |
| Telemetry | `POST /telemetry`, `POST /telemetry/synchronize`, `POST /telemetry/batch` |
| Engine state | `GET /engines/{id}/latest`, `/history`, `/state` |
| Simulation | `POST /simulations`, configuration and deterministic replay endpoints |
| Mission history | mission listing, paged replay, and mission report endpoints |
| Stateful replay | create, status, pause, resume, seek, advance, and report endpoints |
| Model evidence | `GET /model/report` (reports release failure rather than hiding it) |
| Adapters | `GET /adapters/health`, `POST /adapters/packets` |

Interactive endpoint schemas are available at `http://127.0.0.1:8000/docs` when running.

## 7. Security design

Except for health/demo status and token acquisition, operations use time-limited bearer tokens and server-side role checks. Roles are Admin, Operator, Analyst, Maintenance Engineer, and Viewer, with endpoint permissions selected according to the operation.

Security mechanisms include:

- salted password hashing using Python cryptographic primitives;
- signed, expiring bearer tokens;
- token signature and expiration checks;
- environment-provided bootstrap administrator;
- request IDs;
- per-request audit events;
- authentication rate limiting; and
- strict production startup checks requiring a persistent secret of at least 32 characters.

CORS is restricted to the local development origins on ports 3000 and 5173, with GET/POST methods. The local launcher supplies demo credentials and a development-only token secret; these defaults must not be used for production. See `backend/SECURITY.md` for the full threat/production discussion.

## 8. Frontend implementation

### Cinematic aircraft experience

The root `/` experience is a lazy-loaded Three.js scene. React Three Fiber owns the canvas; Drei creates environment lighting; procedural components build the UAV, engine, propellers, and clouds. GSAP ScrollTrigger maps page progress to the aircraft flight and engine-camera sequence, while Lenis supplies smooth scrolling.

The state progression is:

```text
INTRO -> AIRCRAFT_FLIGHT -> AIRCRAFT_SETTLED
                                  |
                            user selects aircraft
                                  v
AIRCRAFT_SELECTED -> ENGINE_ZOOM -> ENGINE_HERO -> workspace
```

The timeline is reversible by scrolling upward. Selection is a gate before engine zoom. The canvas caps device-pixel ratio at 1.5, per-frame 3D transforms use mutable refs to avoid React rerender overhead, and the scene is lazy-loaded. React StrictMode is intentionally not used because its development remount cycle would discard and recreate the scarce WebGL context.

### Engineering workspace

The dashboard mixes TypeScript/TSX with the JSX introduction. It implements navigation with `history.pushState` and `popstate` instead of React Router. Pages include overview/twin, telemetry, health, diagnostics, RUL, simulation, replay, performance, maintenance, reports, settings/architecture, CAN monitor, fleet, and “why it matters.”

The lightweight external store uses `useSyncExternalStore`. It retains up to 240 chart samples and up to 14,400 recording frames. Modes are:

- **REAL**: polls the latest backend history sample, or uses a configured WebSocket URL;
- **SIMULATION**: displays backend simulation frames or a local demonstration frame generator; and
- **REPLAY**: plays stored/recorded frames with seek and speed controls.

Polling uses an abort signal and exponential backoff up to 30 seconds. Incoming timestamps must advance, stale data is visibly marked after 10 seconds, authentication changes reset polling state, and WebSocket reconnects use exponential backoff. API responses are normalized into one frontend `Frame` contract with units and quality flags.

In development, Vite proxies `/api` to `DIGITAL_TWIN_API_TARGET` or `http://127.0.0.1:8000`. The UI does not fabricate unsupported backend capabilities: for example, it says when raw CAN frames, fleet inventory, vibration FFT, or verified hardware are unavailable.

## 9. Project structure

```text
aircraft/
├── frontend/
│   ├── src/components/       procedural Three.js aircraft scene
│   ├── src/animation/        scroll, flight, and camera timelines
│   ├── src/state/            cinematic experience state
│   ├── src/workspace/        dashboard, API client, store, charts, panels
│   ├── tests/ and e2e/       Node and Playwright tests
│   └── package.json          frontend dependencies/scripts
├── backend/
│   ├── app/                  API, twin core, physics, fusion, diagnostics
│   │   └── adapters/         simulator/CAN/SocketCAN/FADEC boundaries
│   ├── dataset/              synthetic generator, CSVs, validation, graphs
│   ├── model_evaluation/     offline ML training, evaluation, artifact/reports
│   └── tests/                backend and integration tests
├── requirements.txt         Python dependencies
├── run_project.ps1/.bat     combined Windows launcher
├── run_backend.bat          backend-only launcher
└── DEMO_GUIDE.md            presentation walkthrough
```

## 10. Running the project

From the repository root on Windows:

```powershell
.\run_project.bat
```

The launcher creates `.venv` if necessary, installs missing backend/frontend dependencies, sets development/demo environment variables, starts FastAPI on port 8000, waits for its health response, and starts Vite on port 5173. Open:

- application: `http://127.0.0.1:5173`
- API docs: `http://127.0.0.1:8000/docs`
- health endpoint: `http://127.0.0.1:8000/api/v1/health`

Custom first-run local credentials can be supplied with:

```powershell
.\run_project.ps1 -Username "admin" -Password "YourStrongLocalPassword"
```

The bootstrap account is only created if the configured database contains no users; changing command-line credentials later does not overwrite it.

## 11. Verification commands

```powershell
# All Python tests
python -m pytest -q

# Validate generated data
python -m backend.dataset.validate_dataset

# Regenerate data (overwrites generated dataset outputs)
python -m backend.dataset.generate_dataset

# Retrain/evaluate offline candidate; expected to exit 2 while its gate fails
python -m backend.model_evaluation.evaluate_fault_classifier

# Frontend checks
cd frontend
npm.cmd test
npm.cmd run build
npx.cmd playwright install chromium
npm.cmd run test:e2e
```

Backend tests cover APIs, authentication/RBAC, adapters, physics, quality handling, sensor fusion, diagnostics, twin state, simulations, replay, and frontend synchronization. Dataset and model-evaluation tests check reproducibility and split/leakage integrity. Browser tests cover scroll reversal, the click gate, responsive behavior, overflow, errors, refresh behavior, and the workspace.

## 12. Configuration

Important environment variables include:

| Variable | Purpose |
|---|---|
| `DIGITAL_TWIN_ENV` | `development` or `production` |
| `DIGITAL_TWIN_DB` | SQLite database path |
| `DIGITAL_TWIN_TOKEN_SECRET` | bearer-token signing secret |
| `DIGITAL_TWIN_TOKEN_MINUTES` | token lifetime |
| `DIGITAL_TWIN_RATE_LIMIT` | requests per minute |
| `DIGITAL_TWIN_BOOTSTRAP_ADMIN_USERNAME` | initial admin username |
| `DIGITAL_TWIN_BOOTSTRAP_ADMIN_PASSWORD` | initial admin password |
| `DIGITAL_TWIN_DEMO_MODE` | enables local dataset demo behavior |
| `DIGITAL_TWIN_DEMO_MISSION` | bundled mission fed in demo mode |
| `DIGITAL_TWIN_ADAPTER` | simulator/CAN/SocketCAN/FADEC selection |
| `DIGITAL_TWIN_CAN_MAPPING` | CAN signal-map path |
| `DIGITAL_TWIN_SOCKETCAN_CHANNEL` | SocketCAN channel |
| `DIGITAL_TWIN_API_TARGET` | Vite development proxy target |
| `VITE_WS_URL` | optional frontend telemetry WebSocket URL |

Engineering behavior is separately configurable through `engineering_thresholds.json`, `prototype_physics_assumptions.json`, `sensor_fusion_assumptions.json`, and `diagnostic_assumptions.json`. Versioning these files is important because changing their values changes model behavior.

## 13. Honest limitations and production gaps

- All flight/engine data is synthetic; no real aircraft or manufacturer dataset is included.
- Physics is a first-order relative model, not CFD, a cycle solver, HIL, or a validated engine map.
- Thresholds and health/RUL outputs are hypotheses and proxies.
- The offline classifier is trained only on synthetic data, is uncalibrated, failed its per-class recall gate, and is not connected to live diagnostics.
- The live hybrid diagnostic engine is explainable but unvalidated; engineering scores are not probabilities.
- Dataset generation introduces only one fault per mission, limiting compound-fault realism.
- Scalar vibration RMS is available, but waveform/frequency-order analysis is not implemented.
- CAN mapping is synthetic; SocketCAN and FADEC require real transport and authorized protocol specifications.
- SQLite and the in-process store/locks are appropriate for a local prototype, not a distributed fleet platform.
- No production deployment definition, managed database, message broker, observability stack, secrets manager, TLS termination, or CI workflow is present.
- The custom client router and store are intentionally lightweight and would need broader hardening for a large application.
- Procedural aircraft/engine meshes are conceptual and do not represent an approved manufacturer's geometry.

## 14. End-to-end summary

When the combined launcher starts, FastAPI initializes configuration, SQLite storage, authentication, the selected adapter, the twin processor, and optional demo dataset feed. Vite serves the React application and proxies `/api`. The user enters through a WebGL aircraft sequence and opens the workspace. Telemetry—whether demo, simulated, historical, adapter-originated, or API-submitted—is validated, assigned explicit quality state, evaluated by the prototype physics model, fused into subsystem health, assessed by explainable diagnostics, assembled into a synchronized twin state, persisted where requested, and exposed as JSON. The frontend normalizes that JSON into a common frame, keeps bounded history, and renders engineering metrics, charts, faults, 3D state, simulation, and replay controls.

That is the complete implemented stack: a local full-stack digital-twin demonstrator with procedural 3D visualization, typed web UI, validated telemetry APIs, synthetic engineering models/data, explainable live diagnostics, and a deliberately quarantined offline ML candidate.
