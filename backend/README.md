# AERION backend

FastAPI ingests validated engine telemetry, calculates a prototype physics and engineering-rule assessment, optionally runs a trusted **research-only** classifier, and stores telemetry, state, and diagnostic results in SQLite. All data and model evidence are synthetic; this service is not flight-certified.

## Local startup

From the repository root in PowerShell, install dependencies if needed and start in fallback mode:

```powershell
cd 'D:\projects D\aircraft'
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:AERION_ENABLE_ML_DIAGNOSTICS='0'
$env:DIGITAL_TWIN_DB=Join-Path $env:TEMP 'aerion-local.db'
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

An existing `.venv` can be reused; creating it again is unnecessary. The service can start without a model in fallback mode. Set `DIGITAL_TWIN_DEMO_MODE='true'` before startup to feed the bundled mission into `DATASET_ENGINE_010` automatically. Demo mode bypasses route authorization for local presentation and clears that demo engine's stream on restart. Keep demo mode off when testing authentication or durable, separately ingested engine history.

For an explicit research ML run, set these **before** starting Uvicorn:

```powershell
$env:AERION_ENABLE_ML_DIAGNOSTICS='1'
$env:DIGITAL_TWIN_ML_ALLOW_UNVALIDATED='true'
```

The prior `DIGITAL_TWIN_ML_ENABLED` variable remains an alias when `AERION_ENABLE_ML_DIAGNOSTICS` is unset. Both flags default to off. The runtime trusts only `model_evaluation/outputs/live_candidate/model.joblib`: it checks SHA-256, evaluation sidecar, scikit-learn version 1.9.1, ordered `live-telemetry-v1` features, and class mapping before inference. A missing or incompatible model leaves engineering fallback available. Production refuses the unvalidated-model override. Do not deserialize arbitrary uploaded joblib files.

## API contract

Interactive OpenAPI documentation is at `http://127.0.0.1:8000/docs`.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/health` | Liveness and prototype mode |
| `GET /api/v1/ready` | Database, adapter, diagnostic mode, and ML readiness; HTTP 503 when core dependencies are unavailable |
| `POST /api/v1/telemetry` | Validate and persist one sample; returns a `TwinAssessment` |
| `POST /api/v1/telemetry/synchronize` | Return telemetry, assessment, and quality-aware twin state for one sample |
| `GET /api/v1/engines/{engine_id}/latest` | Latest persisted sample and assessment |
| `GET /api/v1/engines/{engine_id}/history?limit=20` | Bounded persisted telemetry and diagnostic history |
| `GET /api/v1/engines/{engine_id}/state` | Latest in-memory synchronized state |
| `GET /api/v1/model/report` | Stored evaluation and failed release-gate evidence |
| `POST /api/v1/simulations` | Deterministic generated mission through the same diagnostic processor; saves an immutable mission snapshot |
| `POST /api/v1/replays` | Replay recorded simulation telemetry with current diagnostics; results are labelled re-analysis |
| `GET /api/v1/missions/{mission_id}/report` | Prototype mission summary and diagnostic report |
| `POST /api/v1/missions/compare` | Re-analyze two missions without retaining replay sessions; return both reports and descriptive differences |

Other existing routes cover bearer authentication, adapter packets, mission replay, and reports. Except for health, readiness, demo status, and token acquisition, routes require bearer authentication when demo mode is off. Set `DIGITAL_TWIN_BOOTSTRAP_ADMIN_USERNAME` and `DIGITAL_TWIN_BOOTSTRAP_ADMIN_PASSWORD` before first startup with a new database, then obtain a token through `POST /api/v1/auth/token`. See [SECURITY.md](SECURITY.md) for roles and development limitations.

`FULL_MISSION` is the runtime profile with start-to-shutdown phases; other profiles retain their earlier conditions. Simulation responses include `generator_version`, per-sample `scenario_truth`, and `fault_onset_seconds` for injected synthetic faults. The [scenario mapping](app/SCENARIOS.md) distinguishes runtime scenarios, historical dataset classes, and engineering rule codes. These synthetic truth fields are not ML inference features.

`TwinAssessment.predicted_fault` remains the engineering-rule diagnosis for older clients. The typed `diagnostic_result` gives the displayed source (`engineering_rules`, `ml_research`, or `unavailable`), class, score kind, model version where applicable, sensor quality, and warning. Research ML scores are **uncalibrated**, not failure probabilities. `confidence` is null because a calibrated aggregate confidence has not been established. Severity belongs to engineering diagnostic records; the classifier does not supply a validated severity estimate. Invalid or stale required telemetry gives an unavailable result instead of a plausible-looking diagnosis.

The SQLite store uses schema version 3. The migration preserves existing telemetry and adds `simulation_snapshots`; it does not clear ordinary engine history. New missions save the exact generated telemetry, assessments, and twin states. Reusing a mission ID with different configuration returns HTTP 409. `/api/v1/simulations/{mission_id}/replay` returns the recorded snapshot, while session replay applies the current diagnostic rules to its recorded telemetry and labels the result as re-analysis. The optional `persist=true` on direct replay adds that re-analysis to engine history and marks `reanalysis_persisted`; repeated calls add repeated entries. Interactive replay sessions are capped at 32 per process, expire after 30 minutes, and return HTTP 429 when full. Mission reports and comparisons do not retain replay sessions. Legacy configuration-only missions have no saved samples, so their replay is explicitly labelled as regenerated. Direct ingestion persists the assessment, including `diagnostic_result`. History requests have explicit limits. The default database is `backend/runtime/digital_twin.db`; choose `DIGITAL_TWIN_DB` for an isolated development database.

## Verification and model limits

```powershell
cd 'D:\projects D\aircraft'
.\.venv\Scripts\python.exe -m pytest backend/tests/test_application_pipeline.py backend/tests/test_api.py backend/tests/test_ml_diagnostics.py -q
```

The implementation report records **26 passing focused tests**, a fresh fallback HTTP startup and persistence check, and a research-mode API/browser demonstration. See [PHASE2_IMPLEMENTATION_REPORT.md](PHASE2_IMPLEMENTATION_REPORT.md). The full historical suite has version-specific tests for scikit-learn 1.7.2 and 1.9.1; run each group in its matching environment as recorded there.

The integrated live-compatible candidate fails the frozen 0.80 per-class recall gate. Stage 6 Candidate B remains blocked by the [independent audit](model_evaluation/outputs_stage6/stage6_independent_audit.md). No real-aircraft dataset or airworthiness evidence is supplied. For dataset and offline-evaluation provenance, use the [dataset guide](dataset/README.md) and [model-evaluation guide](model_evaluation/README.md). Read-only validation is preferred; historical outputs must not be overwritten during routine verification.
