# Operational Runbook: Graph-Based Agentic Cash-Flow Intelligence System

This document provides complete, production-grade instructions for setting up, running, testing, and troubleshooting the Graph-Based Cash-Flow Intelligence System (GACI) locally.

---

## 1. System Requirements & Prerequisites

* **Operating System:** Windows 10/11, macOS (Intel/Apple Silicon), or Linux (Ubuntu 22.04+).
* **Python Runtime:** Python 3.11 or 3.12 (Python 3.13 verified compatible).
* **Relational Database:** PostgreSQL 15 or 16 (or built-in SQLite in-memory fallback for offline/isolated execution).
* **Graph Database:** Neo4j Community or Enterprise 5.x (with Bolt protocol enabled; or in-memory NetworkX relational projection fallback).
* **Optional Containerization:** Docker Desktop 4.x and Docker Compose v2.

---

## 2. Environment Setup

### 2.1. Clone Repository & Create Virtual Environment

```bash
# Clone the repository
git clone https://github.com/Pratiksawant14/GACI.git
cd GACI

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate
```

### 2.2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 2.3. Configure Environment Variables

Copy the provided example environment template:
```bash
cp .env.example .env
```

Ensure your `.env` contains valid credentials:
```ini
# Application
ENVIRONMENT=development
LOG_LEVEL=INFO

# PostgreSQL Configuration
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cashflow_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
# Or explicit URL (defaults to SQLite fallback if left empty or offline):
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/cashflow_db

# Neo4j Graph Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Multi-Provider LLM Keys (Cascade Fallback Engine)
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
HUGGINGFACE_API_KEY=your_huggingface_api_key
HUGGINGFACE_MODEL=Qwen/Qwen2.5-72B-Instruct
```

---

## 3. Database Initialization & Migrations

Apply canonical Alembic schema migrations:

```bash
# Upgrade database to latest revision
alembic upgrade head
```

To rollback or reset database migrations:
```bash
# Downgrade to baseline
alembic downgrade base
```

---

## 4. Starting the Application Locally

### Method A: Single Command Launch (Windows)

Double click or run:
```powershell
.\run_local.bat
```

### Method B: Single Command Launch (Linux / macOS)

```bash
chmod +x run_local.sh
./run_local.sh
```

### Method C: Manual Terminal Launch

**Terminal 1 — Backend API (FastAPI):**
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
* Interactive Swagger OpenAPI Docs: `http://127.0.0.1:8000/docs`
* Health Check: `http://127.0.0.1:8000/health`
* Readiness Check: `http://127.0.0.1:8000/ready`

**Terminal 2 — Frontend UI (Streamlit):**
```bash
streamlit run frontend/app.py --server.port 8501 --server.address 127.0.0.1
```
* Dashboard URL: `http://127.0.0.1:8501`

---

## 5. Ingesting Wholesale Sample Data

1. Open the Streamlit dashboard at `http://127.0.0.1:8501`.
2. In the sidebar, click the **"📥 Load Wholesale Sample Data"** button.
3. This automatically ingests:
   - 5 wholesale commercial customers with authorized credit limits
   - 3 primary agricultural/mills suppliers with lead times
   - 3 liquid bank accounts (HDFC Current, SBI CC, Petty Cash)
   - 8 sales invoices with partial payments and overdue balances
   - 4 payment transactions (including a bounced cheque)
   - 3 supplier advances (including a stranded advance without goods delivery)
   - 2 partial delivery fulfillment receipts
   - 4 upcoming financial obligations (GST, Loan EMI, Payroll, Rent)
4. Or trigger manual sync from the REST API:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/graph/sync
   ```

---

## 6. Running with Docker Compose

To launch all 4 services (PostgreSQL 16, Neo4j 5.26, FastAPI backend, and Streamlit frontend) in containers:

```bash
# Build and start services in background
docker compose up -d

# Check running services
docker compose ps

# View service logs
docker compose logs -f api
docker compose logs -f frontend

# Teardown containers and clean volumes
docker compose down -v
```

---

## 7. Running Test Suites

Execute the entire automated test suite (47 tests across 9 modules):

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run only end-to-end acceptance scenarios
pytest tests/e2e/test_scenarios.py -v

# Run tests with test coverage report
pytest --cov=app tests/
```

---

## 8. Troubleshooting & Common Issues

| Issue | Root Cause | Resolution |
| :--- | :--- | :--- |
| **Neo4j connection timeout** | Neo4j service is offline or not installed locally. | GACI automatically falls back to the in-memory NetworkX relational projection without crashing. To use live Neo4j, run `docker compose up -d neo4j`. |
| **`HTTP 429` on OpenRouter** | Free LLM provider rate limit exceeded. | GACI's `MultiProviderLLMClient` automatically cascades to Gemini, Hugging Face, or deterministic grounded synthesis with 0 downtime. |
| **`sqlite3.OperationalError: no such table` in tests** | Multi-threaded test runner lost table reference. | Verify `tests/conftest.py` uses `StaticPool` with `check_same_thread=False`. |
| **Upload file validation error** | Uploaded CSV has invalid dates (`due_date < issue_date`). | Check `ingestion_logs` table or the Ingestion tab error report for exact row number and validation error details. |
