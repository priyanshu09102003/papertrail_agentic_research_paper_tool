$backendDir = Join-Path $PSScriptRoot "backend"
Set-Location $backendDir
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Starting PaperTrail FastAPI Backend on Port 8000" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$venvUvicorn = Join-Path $backendDir ".venv\Scripts\uvicorn.exe"
if (Test-Path $venvUvicorn) {
    Write-Host "Using backend virtual environment (.venv)..." -ForegroundColor Green
    & $venvUvicorn app.main:app --reload --port 8000
} else {
    Write-Host "Using system Python uvicorn..." -ForegroundColor Yellow
    uvicorn app.main:app --reload --port 8000
}
