param(
    [string]$Username = "admin",
    [string]$Password = "AerionLocalDemo!2026"
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$frontendDir = Join-Path $projectRoot "frontend"

Set-Location $projectRoot

if (-not (Test-Path $venvPython)) {
    Write-Host "[SETUP] Creating Python virtual environment..."
    python -m venv .venv
}

$savedErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $venvPython -c "import fastapi, uvicorn" 2>$null
$dependenciesReady = $LASTEXITCODE -eq 0
$ErrorActionPreference = $savedErrorPreference
if (-not $dependenciesReady) {
    Write-Host "[SETUP] Installing backend dependencies..."
    & $venvPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }
}

if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "[SETUP] Installing frontend dependencies..."
    Push-Location $frontendDir
    try { npm.cmd install } finally { Pop-Location }
}

$env:DIGITAL_TWIN_ENV = "development"
$env:DIGITAL_TWIN_DEMO_MODE = "true"
$env:DIGITAL_TWIN_DEMO_MISSION = "MISSION_0110"
$env:DIGITAL_TWIN_DB = Join-Path $projectRoot "backend\runtime\local-development.db"
$env:DIGITAL_TWIN_TOKEN_SECRET = "local-development-secret-change-before-production"
$env:DIGITAL_TWIN_BOOTSTRAP_ADMIN_USERNAME = $Username
$env:DIGITAL_TWIN_BOOTSTRAP_ADMIN_PASSWORD = $Password

Write-Host "[START] Backend: http://127.0.0.1:8000"
$backend = Start-Process -FilePath $venvPython `
    -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($backend.HasExited) { throw "The backend stopped during startup." }
        try {
            $health = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/health" -TimeoutSec 1
            if ($health.status -eq "ok") { $ready = $true; break }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) { throw "The backend did not become ready at port 8000." }

    Write-Host "[READY] Sign in at System Configuration with: $Username / $Password"
    Write-Host "[START] Frontend: http://127.0.0.1:5173"
    Write-Host "[STOP] Press Ctrl+C to stop both services."
    Set-Location $frontendDir
    npm.cmd run dev
} finally {
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id
    }
}
