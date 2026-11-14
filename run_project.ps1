param(
    [string]$Username = "admin",
    [string]$Password = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
$frontendDir = Join-Path $projectRoot "frontend"

Set-Location $projectRoot

foreach ($port in 8000, 5173) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $attempt = $client.BeginConnect("127.0.0.1", $port, $null, $null)
        if ($attempt.AsyncWaitHandle.WaitOne(500) -and $client.Connected) {
            throw "Port $port is already in use. Stop the existing service before starting this project."
        }
    } finally { $client.Dispose() }
}

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "npm was not found. Install Node.js 22 and try again."
}

if (-not (Test-Path $venvPython)) {
    Write-Host "[SETUP] Creating Python virtual environment..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Python virtual environment creation failed." }
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
    try {
        npm.cmd install
        if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
    } finally { Pop-Location }
}

$env:DIGITAL_TWIN_ENV = "development"
$env:DIGITAL_TWIN_DEMO_MODE = "true"
$env:DIGITAL_TWIN_DEMO_MISSION = "MISSION_0110"
if (-not $env:DIGITAL_TWIN_DB) {
    $env:DIGITAL_TWIN_DB = Join-Path $projectRoot "start-local.db"
}
if ($Password) {
    $env:DIGITAL_TWIN_BOOTSTRAP_ADMIN_USERNAME = $Username
    $env:DIGITAL_TWIN_BOOTSTRAP_ADMIN_PASSWORD = $Password
} else {
    Remove-Item Env:DIGITAL_TWIN_BOOTSTRAP_ADMIN_PASSWORD -ErrorAction SilentlyContinue
}

Write-Host "[START] Backend: http://127.0.0.1:8000"
$backend = Start-Process -FilePath $venvPython `
    -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($backend.HasExited) { throw "The backend stopped during startup." }
        try {
            $readiness = Invoke-RestMethod "http://127.0.0.1:8000/api/v1/ready" -TimeoutSec 1
            if ($readiness.status -eq "ready") { $ready = $true; break }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) { throw "The backend did not become ready at port 8000." }

    Write-Host "[READY] Local demo mode is active. Authenticated setup requires an explicitly supplied bootstrap password."
    Write-Host "[START] Frontend: http://127.0.0.1:5173"
    Write-Host "[STOP] Press Ctrl+C to stop both services."
    Set-Location $frontendDir
    npm.cmd run dev -- --port 5173 --strictPort
    if ($LASTEXITCODE -ne 0) { throw "Frontend server exited with code $LASTEXITCODE." }
} finally {
    if ($backend -and -not $backend.HasExited) {
        Stop-Process -Id $backend.Id
    }
}
