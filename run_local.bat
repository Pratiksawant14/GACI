@echo off
REM ==============================================================================
REM Local Startup Script for Cash-Flow Intelligence System (Windows PowerShell/CMD)
REM ==============================================================================

echo [GACI] Starting Cash-Flow Intelligence System...

echo [GACI] Applying database migrations...
alembic upgrade head

echo [GACI] Launching FastAPI backend server on http://127.0.0.1:8000 in background...
start "GACI Backend (FastAPI)" cmd /k "uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak > nul

echo [GACI] Launching Streamlit frontend dashboard on http://127.0.0.1:8501...
streamlit run frontend/app.py --server.port 8501 --server.address 127.0.0.1

pause
