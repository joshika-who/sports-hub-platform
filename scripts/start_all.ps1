# Start Sports Hub Platform (Backend + Frontend) on Windows PowerShell
$ErrorActionPreference = "Continue"
$RootDir = Split-Path -Parent $PSScriptRoot
Set-Location $RootDir

Write-Host "=== Starting Sports Hub Platform ===" -ForegroundColor Cyan

# Ensure local Node is in PATH if installed in .tools/node
$LocalNodeDir = Join-Path $RootDir ".tools\node"
if (Test-Path $LocalNodeDir) {
    $env:PATH = "$LocalNodeDir;$env:PATH"
}

# 1. Backend setup & start
$BackendDir = Join-Path $RootDir "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "[Backend] Creating virtual environment..." -ForegroundColor Yellow
    Set-Location $BackendDir
    python -m venv .venv
    & $VenvPython -m pip install -r requirements.txt
}

Write-Host "[Backend] Launching FastAPI on http://localhost:8000 ..." -ForegroundColor Green
Start-Process -FilePath $VenvPython -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload" -WorkingDirectory $BackendDir

# 2. Frontend start
$FrontendDir = Join-Path $RootDir "frontend"
Write-Host "[Frontend] Launching Next.js on http://localhost:3000 ..." -ForegroundColor Green
Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" -WorkingDirectory $FrontendDir

Write-Host "Both services started! Backend: http://localhost:8000/docs | Frontend: http://localhost:3000" -ForegroundColor Cyan

