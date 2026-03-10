param(
    [switch]$InstallDeps,
    [ValidateSet("warn", "strict")]
    [string]$ValidationMode = "warn"
)

$root = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $root ".venv\Scripts\python.exe"
$alembicExe = Join-Path $root ".venv\Scripts\alembic.exe"
$frontendDir = Join-Path $root "frontend"
$pidFile = Join-Path $root ".demo-processes.json"

if (-not (Test-Path $pythonExe)) {
    Write-Error "Python executable not found at $pythonExe"
    exit 1
}

if (-not (Test-Path $frontendDir)) {
    Write-Error "Frontend directory not found at $frontendDir"
    exit 1
}

if (-not (Test-Path $alembicExe)) {
    Write-Error "Alembic executable not found at $alembicExe"
    exit 1
}

Write-Host "Stopping any stale demo processes..."
powershell -ExecutionPolicy Bypass -File (Join-Path $root "scripts\stop-demo.ps1") | Out-Null

if ($InstallDeps) {
    Write-Host "Installing backend dependencies..."
    & $pythonExe -m pip install -r (Join-Path $root "backend\requirements.txt")

    Write-Host "Installing frontend dependencies..."
    Push-Location $frontendDir
    npm install
    Pop-Location
}

Write-Host "Applying backend migrations..."
Push-Location (Join-Path $root "backend")
& $alembicExe -c alembic.ini upgrade head
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Error "Failed to apply backend migrations."
    exit 1
}
Pop-Location

$backendCmd = "Set-Location '$root'; `$env:ENV_VALIDATION_MODE='$ValidationMode'; & '$pythonExe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000"
$frontendCmd = "Set-Location '$frontendDir'; npm run dev"

Write-Host "Starting backend on http://127.0.0.1:8000 (ENV_VALIDATION_MODE=$ValidationMode)"
$backendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -PassThru

Write-Host "Waiting for backend health..."
$healthy = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2
        if ($res.StatusCode -eq 200) {
            $healthy = $true
            break
        }
    }
    catch {
    }
}

if (-not $healthy) {
    Write-Error "Backend did not become healthy at http://127.0.0.1:8000/health within 30s"
    exit 1
}

Write-Host "Starting frontend on http://127.0.0.1:5173"
$frontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -PassThru

Write-Host "Waiting for frontend readiness..."
$frontendReady = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $res = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -UseBasicParsing -TimeoutSec 2
        if ($res.StatusCode -ge 200 -and $res.StatusCode -lt 500) {
            $frontendReady = $true
            break
        }
    }
    catch {
    }
}

if (-not $frontendReady) {
    Write-Warning "Frontend did not become reachable at http://127.0.0.1:5173 within 30s"
}

@{
    backendPid = $backendProcess.Id
    frontendPid = $frontendProcess.Id
    updatedAt = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8

Write-Host "Demo services launched in new terminals."
