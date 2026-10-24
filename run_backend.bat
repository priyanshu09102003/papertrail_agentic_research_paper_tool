@echo off
setlocal
cd /d "%~dp0backend"
echo ===================================================
echo   Starting PaperTrail FastAPI Backend on Port 8000
echo ===================================================
if exist .venv\Scripts\uvicorn.exe (
    echo Using backend virtual environment (.venv)...
    .\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
) else (
    echo Using system Python uvicorn...
    uvicorn app.main:app --reload --port 8000
)
pause
