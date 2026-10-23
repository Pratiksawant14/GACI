#!/usr/bin/env bash
# ==============================================================================
# Local Startup Script for Cash-Flow Intelligence System (Linux / macOS)
# ==============================================================================
set -e

echo "Starting Cash-Flow Intelligence System..."

# Run database migrations
echo "Applying database migrations..."
alembic upgrade head

# Start FastAPI in background
echo "Starting FastAPI backend at http://127.0.0.1:8000..."
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
API_PID=$!

# Start Streamlit frontend
echo "Starting Streamlit dashboard at http://127.0.0.1:8501..."
streamlit run frontend/app.py --server.port 8501 --server.address 127.0.0.1

# Cleanup on exit
trap "kill $API_PID" EXIT
