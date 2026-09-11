@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [SETUP] Creating virtual environment...
  python -m venv .venv || exit /b 1
)

call ".venv\Scripts\activate.bat" || exit /b 1
python -c "import fastapi,uvicorn" >nul 2>nul
if errorlevel 1 (
  echo [SETUP] Installing backend dependencies...
  python -m pip install --upgrade pip || exit /b 1
  python -m pip install -r requirements.txt || exit /b 1
)

echo [START] API: http://127.0.0.1:8000  Docs: http://127.0.0.1:8000/docs
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
exit /b %errorlevel%

