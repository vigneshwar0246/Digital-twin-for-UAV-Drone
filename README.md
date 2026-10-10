# AERION digital twin

## Run frontend and backend together (Windows)

From the repository root:

```powershell
.\run_project.bat
```

Open `http://127.0.0.1:5173`, enter the digital-twin workspace, then open
the digital-twin workspace. Local judge-demo mode requires no sign-in and feeds
the bundled mission dataset automatically. See [`DEMO_GUIDE.md`](DEMO_GUIDE.md)
for the presentation walkthrough.

The launcher creates `.venv`, installs missing dependencies, starts FastAPI on
port 8000, waits for its health endpoint, and starts Vite on port 5173. Vite
proxies `/api` to the backend. Press Ctrl+C in the terminal to stop both.

To choose local development credentials on the first run:

```powershell
.\run_project.ps1 -Username "admin" -Password "YourStrongLocalPassword"
```

The combined launcher uses `backend/runtime/local-development.db`. The bootstrap
user is only created when that database has no users. Changing these arguments
later does not reset an existing account.

## Run in separate terminals

Backend terminal (repository root):

```powershell
$env:DIGITAL_TWIN_BOOTSTRAP_ADMIN_USERNAME = "admin"
$env:DIGITAL_TWIN_BOOTSTRAP_ADMIN_PASSWORD = "AerionLocalDemo!2026"
.\run_backend.bat
```

Frontend terminal:

```powershell
cd .\frontend
npm.cmd install
npm.cmd run dev
```

Useful URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend API docs: `http://127.0.0.1:8000/docs`
- Backend health: `http://127.0.0.1:8000/api/v1/health`

## ML diagnostics status

The dataset is synthetic. The existing offline histogram-gradient-boosting classifier remains the benchmark and **fails** the project's 0.80 per-fault recall gate. A bounded search over two histogram-boosting settings and Extra Trees using only live API telemetry fields also failed. Its best validation model performs worse than the benchmark, so no ML classifier is approved for operational use.

The backend has an optional, version-checked ML provider. It loads the exploratory artifact once per process and reports its prediction separately from engineering rules and statistical diagnostics. It does not change the engineering fault assessment, and its output is an uncalibrated model score, not a failure probability. Live ML is disabled by default. To inspect the candidate in a **development** environment only, set both `DIGITAL_TWIN_ML_ENABLED=true` and `DIGITAL_TWIN_ML_ALLOW_UNVALIDATED=true` before starting the backend. Leave either unset to keep the rule/statistical fallback. Missing or incompatible artifacts and invalid or stale telemetry produce an unavailable or blocked ML status.

Reproduce the evaluations from the repository root:

```powershell
.\.venv\Scripts\python.exe -m backend.dataset.validate_dataset
.\.venv\Scripts\python.exe -m backend.model_evaluation.evaluate_fault_classifier
.\.venv\Scripts\python.exe -m backend.model_evaluation.live_candidate
.\.venv\Scripts\python.exe -m backend.model_evaluation.render_live_candidate
```

The original evaluator exits nonzero when its release gate fails. See [the evaluation guide](backend/model_evaluation/README.md) for measured results, split policy, and artifact details.
