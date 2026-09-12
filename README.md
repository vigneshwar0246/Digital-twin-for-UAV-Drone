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
