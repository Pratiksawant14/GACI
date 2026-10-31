#!/bin/bash
set -e

echo "=========================================================="
echo "Starting GACI MSME Cash-Flow Intelligence System"
echo "=========================================================="

# Create data directories if needed
mkdir -p /app/data

# 1. Start FastAPI backend in background on port 8000
echo "[1/2] Starting FastAPI backend on http://127.0.0.1:8000 ..."
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Wait for FastAPI to be fully healthy
echo "Waiting for backend health check..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8000/api/v1/health > /dev/null 2>&1; then
        echo " Backend is ONLINE and healthy!"
        break
    fi
    sleep 1
done

# 2. Start Streamlit frontend on port 7860 (Hugging Face Spaces default public port)
echo "[2/2] Starting Streamlit frontend on port 7860 ..."
export API_BASE_URL="http://127.0.0.1:8000"

exec streamlit run frontend/app.py \
    --server.port=7860 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --browser.gatherUsageStats=false
