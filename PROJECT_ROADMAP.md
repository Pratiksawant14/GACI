# PROJECT_ROADMAP.md — Hierarchical Implementation Plan

**Project Title:** Graph-Based Agentic Cash-Flow Intelligence System for Small Wholesale MSMEs  
**Version:** 1.0.0 (Baseline Implementation Plan)  
**Status:** DRAFT BASELINE (Awaiting User Review & Approval)  

Hierarchy Structure:
* **Phase (`PH-xx`)**
  * **Epic (`EP-xx`)**
    * **Story (`ST-xx`)**
      * **Task (`TSK-xx`)**
        * **Subtask (`SUB-xx`)**

---

## Phase 1: Project Foundation, Environment & Verification (`PH-01`)

### Epic 1: Project Scaffold & Environment Setup (`EP-01`)
* **Purpose:** Establish a robust Python project structure, virtual environment, dependency management, configuration validation, and foundational test runner.
* **Scope:** Python dependencies, directory layout, `.env` schema, Pydantic settings, and pytest configuration.
* **Prerequisites:** Python 3.10+, Git.
* **Stories:** `ST-01`, `ST-02`
* **Definition of Done:** Project initializes cleanly, dependencies install without conflict, configuration loads safely, and a baseline test passes.

#### Story 1: Directory Structure & Dependency Configuration (`ST-01`)
* **Outcome:** Clean, modular repository layout with locked dependencies and development tooling.
* **Dependencies:** None.
* **Tasks:**
  * **Task 1: Initialize Directory Layout and Git Ignore (`TSK-01`)**
    * *Instructions:* Create standard layout: `app/` (`core`, `db`, `models`, `schemas`, `services`, `graph`, `analysis`, `agent`, `api`), `frontend/`, `tests/` (`unit`, `integration`, `e2e`), `data/samples/`, and `.gitignore`.
    * *Affected Files:* `.gitignore`, `README.md`, directory trees.
    * *Dependencies:* None.
    * *Completion Criteria:* Directory structure created; Git ignores virtualenvs, caches, credentials, and temp files.
    * *Verification:* Directory listing and `git status`.
    * *Subtasks:*
      - `SUB-01`: Create core application subpackages with `__init__.py`.
      - `SUB-02`: Create tests subdirectories (`unit/`, `integration/`, `e2e/`).
      - `SUB-03`: Create `.gitignore` ignoring `.env`, `__pycache__`, `.pytest_cache/`, `venv/`.
  * **Task 2: Define Project Dependencies (`TSK-02`)**
    * *Instructions:* Define `pyproject.toml` or `requirements.txt` with FastAPI, Uvicorn, SQLAlchemy 2.0+, Alembic, asyncpg / psycopg2-binary, Neo4j driver, NetworkX, LangGraph, LangChain, Pydantic v2, Pandas, OpenPyXL, Streamlit, PyVis, Pytest.
    * *Affected Files:* `requirements.txt`, `requirements-dev.txt`.
    * *Dependencies:* `TSK-01`.
    * *Completion Criteria:* Requirements file created with pinned compatible versions.
    * *Verification:* `pip install -r requirements.txt` succeeds in local virtual environment.
    * *Subtasks:*
      - `SUB-04`: Draft runtime dependencies list.
      - `SUB-05`: Draft test and dev tooling dependencies list.
      - `SUB-06`: Verify package compatibility under Python 3.10-3.13.

#### Story 2: Configuration & Environment Management (`ST-02`)
* **Outcome:** Safe configuration loading with Pydantic BaseSettings, `.env.example`, and baseline health tests.
* **Dependencies:** `ST-01`.
* **Tasks:**
  * **Task 3: Implement Core Settings Module (`TSK-03`)**
    * *Instructions:* Create `app/core/config.py` using `pydantic_settings.BaseSettings`. Define properties for Postgres (`POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`), Neo4j (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`), LLM (`OPENAI_API_KEY`, `LLM_MODEL`), and App settings (`ENVIRONMENT`, `LOG_LEVEL`).
    * *Affected Files:* `app/core/config.py`, `.env.example`.
    * *Dependencies:* `TSK-02`.
    * *Completion Criteria:* `Settings` parses variables with type safety, validates required keys, and defaults safely for local dev.
    * *Verification:* Unit test loading `.env.example` defaults.
    * *Subtasks:*
      - `SUB-07`: Build `Settings` class with Pydantic v2.
      - `SUB-08`: Create `.env.example` with safe placeholder documentation.
      - `SUB-09`: Configure application logger in `app/core/logging.py`.
  * **Task 4: Setup Testing Harness and Health Check (`TSK-04`)**
    * *Instructions:* Create `tests/conftest.py` with pytest fixtures for settings and temporary directories. Create `tests/unit/test_config.py`.
    * *Affected Files:* `tests/conftest.py`, `tests/unit/test_config.py`, `pytest.ini`.
    * *Dependencies:* `TSK-03`.
    * *Completion Criteria:* `pytest` runs and executes `test_config.py` successfully.
    * *Verification:* Run `pytest tests/unit`.
    * *Subtasks:*
      - `SUB-10`: Create `pytest.ini` with testpaths and asyncio mode.
      - `SUB-11`: Implement `tests/unit/test_config.py`.
      - `SUB-12`: Execute test suite and verify 100% pass rate.

---

## Phase 2: Relational Data Model & Canonical Persistence (`PH-02`)

### Epic 2: Canonical Database Schema & Migrations (`EP-02`)
* **Purpose:** Establish the PostgreSQL relational schema as the canonical source of truth for wholesale financial and operational records.
* **Scope:** SQLAlchemy ORM models, Alembic migrations, database constraints, double-entry allocations, and local connection pooling.
* **Prerequisites:** `EP-01`.
* **Stories:** `ST-03`, `ST-04`
* **Definition of Done:** PostgreSQL database initialized, migrations applied cleanly, relational models instantiated and verified with unit/integration tests.

#### Story 3: Domain Models & SQLAlchemy Schema (`ST-03`)
* **Outcome:** Comprehensive relational models representing parties, accounts, invoices, payments, advances, deliveries, and obligations.
* **Dependencies:** `ST-02`.
* **Tasks:**
  * **Task 5: Define Canonical Database Models (`TSK-05`)**
    * *Instructions:* Create SQLAlchemy models in `app/models/`:
      - `Business`: Base business entity.
      - `Customer`, `Supplier`: Commercial counterparties.
      - `BankAccount`: Liquid accounts with account type and balance.
      - `SalesInvoice`: Invoices with issue/due dates, total, paid, and status.
      - `Payment`: Financial receipts and disbursements with method and status.
      - `PaymentAllocation`: Links payments to invoices.
      - `SupplierAdvance`: Advances disbursed with expected delivery date.
      - `Delivery`: Goods deliveries fulfilling advances.
      - `FinancialObligation`: Contractual upcoming liabilities.
      - `IngestionLog`: Import history and error tracking.
    * *Affected Files:* `app/models/base.py`, `app/models/entities.py`, `app/models/finance.py`.
    * *Dependencies:* `TSK-04`.
    * *Completion Criteria:* Models define strict primary keys (UUID), foreign keys, check constraints, numeric scale (15,2), and timestamps.
    * *Verification:* Unit test validating model schemas and relations.
    * *Subtasks:*
      - `SUB-13`: Create base model with UUID primary keys and audit timestamps.
      - `SUB-14`: Implement entity models (`Business`, `Customer`, `Supplier`, `BankAccount`).
      - `SUB-15`: Implement transactional models (`SalesInvoice`, `Payment`, `PaymentAllocation`).
      - `SUB-16`: Implement operational models (`SupplierAdvance`, `Delivery`, `FinancialObligation`, `IngestionLog`).
  * **Task 6: Configure Alembic Migration Suite (`TSK-06`)**
    * *Instructions:* Initialize Alembic in `alembic/`, configure `env.py` to import SQLAlchemy metadata, and generate the baseline migration script.
    * *Affected Files:* `alembic.ini`, `alembic/env.py`, `alembic/versions/001_initial_schema.py`.
    * *Dependencies:* `TSK-05`.
    * *Completion Criteria:* Migration applies cleanly (`alembic upgrade head`) and rolls back cleanly (`alembic downgrade base`).
    * *Verification:* Run migration commands against local Postgres or SQLite in-memory test database.
    * *Subtasks:*
      - `SUB-17`: Initialize Alembic environment.
      - `SUB-18`: Configure metadata target in `alembic/env.py`.
      - `SUB-19`: Generate and verify initial schema migration script.

#### Story 4: Relational Repository & Transactional Services (`ST-04`)
* **Outcome:** Repository layer managing transactional operations, idempotency, and query methods for financial analysis.
* **Dependencies:** `ST-03`.
* **Tasks:**
  * **Task 7: Implement Database Session & Base Repository (`TSK-07`)**
    * *Instructions:* Build `app/db/session.py` with SQLAlchemy session factory and connection lifecycle manager. Create repository classes in `app/db/repositories/`.
    * *Affected Files:* `app/db/session.py`, `app/db/repositories/party_repo.py`, `app/db/repositories/finance_repo.py`.
    * *Dependencies:* `TSK-06`.
    * *Completion Criteria:* Session manager provides scoped transactions; repositories support CRUD with conflict handling.
    * *Verification:* Integration test creating and querying records.
    * *Subtasks:*
      - `SUB-20`: Implement session generator and transaction context manager.
      - `SUB-21`: Implement `CustomerRepository` and `SupplierRepository`.
      - `SUB-22`: Implement `InvoiceRepository`, `PaymentRepository`, and `AdvanceRepository`.
      - `SUB-23`: Write tests in `tests/integration/test_repositories.py`.

---

## Phase 3: Temporal Business Graph & Neo4j Projection (`PH-03`)

### Epic 3: Graph Schema & Projection Engine (`EP-03`)
* **Purpose:** Project canonical relational data into Neo4j as a time-aware business graph for relationship traversal and contagion analysis.
* **Scope:** Neo4j driver client, graph constraint setup, idempotent Cypher projection service, and graph verification utilities.
* **Prerequisites:** `EP-02`.
* **Stories:** `ST-05`, `ST-06`
* **Definition of Done:** Neo4j connection verified, constraints created, relational changes projected into graph idempotently, and graph query tests pass.

#### Story 5: Neo4j Driver & Graph Schema Constraints (`ST-05`)
* **Outcome:** Robust Neo4j connection manager with schema constraints ensuring unique node IDs.
* **Dependencies:** `ST-04`.
* **Tasks:**
  * **Task 8: Implement Neo4j Client and Constraint Setup (`TSK-08`)**
    * *Instructions:* Build `app/graph/client.py` using official `neo4j` Python driver. Create initialization routine that asserts uniqueness constraints on `:Business(id)`, `:Customer(id)`, `:Supplier(id)`, `:Invoice(id)`, `:Payment(id)`, `:BankAccount(id)`, `:SupplierAdvance(id)`, `:Obligation(id)`.
    * *Affected Files:* `app/graph/client.py`, `app/graph/schema.py`.
    * *Dependencies:* `TSK-07`.
    * *Completion Criteria:* Client connects, handles retries, and initializes schema constraints without error.
    * *Verification:* Integration test connecting to Neo4j (or mock/fallback) and verifying schema.
    * *Subtasks:*
      - `SUB-24`: Implement `Neo4jClient` with connection pooling and context management.
      - `SUB-25`: Create `init_graph_constraints()` Cypher script.
      - `SUB-26`: Write connection and constraint verification test.

#### Story 6: Idempotent Graph Projection Service (`ST-06`)
* **Outcome:** Service that projects PostgreSQL entities and relationships into Neo4j using atomic Cypher `MERGE` statements.
* **Dependencies:** `ST-05`.
* **Tasks:**
  * **Task 9: Build Graph Projection Service (`TSK-09`)**
    * *Instructions:* Create `app/services/projection_service.py` with methods to project parties, invoices, payments, advances, and obligations. Ensure all Cypher writes are idempotent.
    * *Affected Files:* `app/services/projection_service.py`, `app/graph/cypher_queries.py`.
    * *Dependencies:* `TSK-08`.
    * *Completion Criteria:* Projection synchronizes all relational records into graph nodes and directed edges; re-running projection produces identical node and relationship counts.
    * *Verification:* Integration test inserting relational test records, running projection, and asserting Neo4j subgraph match.
    * *Subtasks:*
      - `SUB-27`: Write Cypher projection templates for nodes and edges.
      - `SUB-28`: Implement entity synchronizers (`sync_parties`, `sync_invoices`, `sync_payments`, `sync_advances`, `sync_obligations`).
      - `SUB-29`: Implement full-graph sync and incremental sync.
      - `SUB-30`: Write tests in `tests/integration/test_projection.py`.

---

## Phase 4: Data Ingestion & Validation Pipeline (`PH-04`)

### Epic 4: Tabular Data Ingestion & Sanitization (`EP-04`)
* **Purpose:** Enable business owners and accountants to upload standard CSV/Excel files with rigorous validation, error reporting, and transactional persistence.
* **Scope:** CSV and Excel parsing, Pydantic row validation, idempotency checks, database persistence, and post-commit graph projection.
* **Prerequisites:** `EP-03`.
* **Stories:** `ST-07`, `ST-08`
* **Definition of Done:** CSV and Excel files can be uploaded via service/API, validated, persisted to PostgreSQL, projected to Neo4j, and row-level errors reported cleanly.

#### Story 7: Ingestion Parsers & Schema Validators (`ST-07`)
* **Outcome:** Type-safe row-level parsers with explicit error reporting for missing fields, bad dates, or negative values.
* **Dependencies:** `ST-06`.
* **Tasks:**
  * **Task 10: Implement Ingestion Row Schemas & Validators (`TSK-10`)**
    * *Instructions:* Create Pydantic validation models in `app/schemas/ingestion.py` for each supported table (Customers, Suppliers, Invoices, Payments, Advances, Deliveries, Obligations, BankAccounts). Implement custom validators for dates and amounts.
    * *Affected Files:* `app/schemas/ingestion.py`.
    * *Dependencies:* `TSK-09`.
    * *Completion Criteria:* Schemas validate correct rows and raise clear, descriptive validation errors for invalid rows.
    * *Verification:* Unit tests validating valid and deliberately malformed inputs.
    * *Subtasks:*
      - `SUB-31`: Implement `CustomerImportRow` and `SupplierImportRow`.
      - `SUB-32`: Implement `InvoiceImportRow` with `due_date >= issue_date` check.
      - `SUB-33`: Implement `PaymentImportRow` and `AdvanceImportRow`.
      - `SUB-34`: Implement `DeliveryImportRow` and `ObligationImportRow`.
      - `SUB-35`: Write unit tests in `tests/unit/test_ingestion_schemas.py`.

#### Story 8: Ingestion Orchestrator & Batch Persistence (`ST-08`)
* **Outcome:** End-to-end ingestion pipeline reading file streams, validating batches, persisting to Postgres, updating graph projection, and logging results.
* **Dependencies:** `ST-07`.
* **Tasks:**
  * **Task 11: Implement Ingestion Service (`TSK-11`)**
    * *Instructions:* Create `app/services/ingestion_service.py` to process file uploads, execute transactional writes with duplicate deduplication, trigger graph synchronization, and write to `ingestion_logs`.
    * *Affected Files:* `app/services/ingestion_service.py`.
    * *Dependencies:* `TSK-10`.
    * *Completion Criteria:* Valid files are ingested and projected; invalid rows are quarantined and reported; identical files re-uploaded produce zero duplicates.
    * *Verification:* Integration test importing test CSV files and verifying both Postgres and Neo4j counts.
    * *Subtasks:*
      - `SUB-36`: Implement CSV and Excel parsing utilities using Pandas/OpenPyXL.
      - `SUB-37`: Build atomic database batch persistence with conflict resolution (`ON CONFLICT DO NOTHING`).
      - `SUB-38`: Connect post-commit graph projection hook.
      - `SUB-39`: Write tests in `tests/integration/test_ingestion_service.py`.
  * **Task 12: Generate Comprehensive Sample Dataset (`TSK-12`)**
    * *Instructions:* Create realistic sample CSV files in `data/samples/` representing a small wholesale distributor (Overdue customer invoices, unfulfilled supplier advances, bounced cheques, upcoming loan EMI).
    * *Affected Files:* `data/samples/*.csv`.
    * *Dependencies:* `TSK-11`.
    * *Completion Criteria:* Realistic dataset covering all 4 core blockage scenarios.
    * *Verification:* Run ingestion service on sample files and verify successful load.
    * *Subtasks:*
      - `SUB-40`: Create `customers.csv` and `suppliers.csv`.
      - `SUB-41`: Create `bank_accounts.csv` and `invoices.csv`.
      - `SUB-42`: Create `payments.csv` (including a bounced cheque).
      - `SUB-43`: Create `advances.csv`, `deliveries.csv`, and `obligations.csv`.

---

## Phase 5: Deterministic Financial & Graph Intelligence (`PH-05`)

### Epic 5: Cash-Blockage & Contagion Engine (`EP-05`)
* **Purpose:** Build deterministic analysis algorithms to identify, quantify, and prioritize working capital blockages and trace causal paths in the graph.
* **Scope:** A/R aging, supplier advance aging, bounced cheque handling, cash pressure forecasting, and Cypher path tracing.
* **Prerequisites:** `EP-04`.
* **Stories:** `ST-09`, `ST-10`
* **Definition of Done:** Deterministic analysis functions compute verified metrics with unit tests; graph queries trace causal links.

#### Story 9: Deterministic Financial Analysis Engine (`ST-09`)
* **Outcome:** Exact calculation of available cash, overdue receivables by bucket, unfulfilled advances, and cash-pressure projections.
* **Dependencies:** `ST-08`.
* **Tasks:**
  * **Task 13: Implement Core Cash Analysis Calculations (`TSK-13`)**
    * *Instructions:* Create `app/analysis/cash_engine.py` with pure deterministic calculation functions:
      - `calculate_liquid_cash()`
      - `calculate_overdue_receivables(aging_buckets=[30, 60, 90])`
      - `calculate_stranded_advances()`
      - `calculate_bounced_cheque_exposure()`
      - `project_cash_flow(window_days=30)`
      - `calculate_blockage_severity_ranking()`
    * *Affected Files:* `app/analysis/cash_engine.py`, `app/schemas/analysis.py`.
    * *Dependencies:* `TSK-12`.
    * *Completion Criteria:* Arithmetic precision verified with Decimal; calculations match manual spreadsheet audit.
    * *Verification:* Comprehensive unit tests in `tests/unit/test_cash_engine.py`.
    * *Subtasks:*
      - `SUB-44`: Implement liquid cash and overdue receivables analysis.
      - `SUB-45`: Implement stranded advances and bounced cheque impact calculations.
      - `SUB-46`: Implement day-by-day cash deficit projection.
      - `SUB-47`: Write unit tests covering edge cases (zero balance, negative cash, partial payments).

#### Story 10: Graph Path Tracing & Bottleneck Intelligence (`ST-10`)
* **Outcome:** Graph queries tracing causal dependencies from overdue customer receipts to upcoming payment shortfalls.
* **Dependencies:** `ST-09`.
* **Tasks:**
  * **Task 14: Implement Graph Contagion Queries (`TSK-14`)**
    * *Instructions:* Create `app/graph/contagion.py` with parameterized Cypher queries:
      - `trace_receivable_to_obligation_paths()`
      - `find_top_counterparty_concentrations()`
      - `detect_circular_credit_links()`
      - `get_entity_subgraph(entity_id)`
    * *Affected Files:* `app/graph/contagion.py`.
    * *Dependencies:* `TSK-13`.
    * *Completion Criteria:* Graph queries return structured paths and subgraphs for downstream explanation and visualization.
    * *Verification:* Integration test asserting path discovery on the sample dataset.
    * *Subtasks:*
      - `SUB-48`: Implement Cypher contagion path query.
      - `SUB-49`: Implement concentration and circular debt queries.
      - `SUB-50`: Implement subgraph extraction query for visualization.
      - `SUB-51`: Write tests in `tests/integration/test_contagion.py`.

---

## Phase 6: FastAPI Backend & Deterministic Tooling (`PH-06`)

### Epic 6: REST API Layer (`EP-06`)
* **Purpose:** Expose RESTful endpoints for data ingestion, financial summaries, blockage diagnostics, graph queries, and agent interaction.
* **Scope:** FastAPI application, routers, error handlers, request validation, and OpenAPI documentation.
* **Prerequisites:** `EP-05`.
* **Stories:** `ST-11`
* **Definition of Done:** All API endpoints implemented, documented via Swagger UI, and verified with FastAPI TestClient tests.

#### Story 11: Backend API Endpoints & Middleware (`ST-11`)
* **Outcome:** Production-grade REST API with robust error handling and structured JSON responses.
* **Dependencies:** `ST-10`.
* **Tasks:**
  * **Task 15: Create FastAPI Application & Routers (`TSK-15`)**
    * *Instructions:* Create `app/main.py` and routers in `app/api/v1/`:
      - `router_health.py`: Health checks (`/health`, `/ready`).
      - `router_ingest.py`: File upload and sync endpoints.
      - `router_analysis.py`: Financial summaries and blockage endpoints.
      - `router_graph.py`: Subgraph query endpoint.
    * *Affected Files:* `app/main.py`, `app/api/v1/*.py`.
    * *Dependencies:* `TSK-14`.
    * *Completion Criteria:* API starts up, serves endpoints, handles errors gracefully, and returns typed responses.
    * *Verification:* Run `pytest tests/integration/test_api.py`.
    * *Subtasks:*
      - `SUB-52`: Set up FastAPI app with CORS and exception handlers.
      - `SUB-53`: Implement health and readiness endpoints.
      - `SUB-54`: Implement ingestion and sync endpoints.
      - `SUB-55`: Implement analysis and graph endpoints.
      - `SUB-56`: Write integration tests using `httpx.AsyncClient` or `TestClient`.

---

## Phase 7: LangGraph Agent & Explainability Workflow (`PH-07`)

### Epic 7: Cash-Flow Intelligence Agent (`EP-07`)
* **Purpose:** Build a stateful LangGraph agent that classifies owner questions, invokes deterministic analysis tools, validates evidence, and generates grounded explanations.
* **Scope:** LangGraph state machine, tool definitions, evidence verification node, prompt templates, and agent API endpoint.
* **Prerequisites:** `EP-06`.
* **Stories:** `ST-12`, `ST-13`
* **Definition of Done:** Agent accurately answers target business questions, cites database records, and gracefully reports missing data without hallucination.

#### Story 12: Deterministic Agent Tools & State Definition (`ST-12`)
* **Outcome:** Typed tool definitions wrapping deterministic analysis functions with rigorous schemas.
* **Dependencies:** `ST-11`.
* **Tasks:**
  * **Task 16: Define Agent Tools and State Schema (`TSK-16`)**
    * *Instructions:* Create `app/agent/tools.py` defining tools:
      - `tool_get_cash_summary`
      - `tool_get_overdue_receivables`
      - `tool_get_stranded_advances`
      - `tool_get_upcoming_obligations`
      - `tool_trace_cash_contagion`
      Create `app/agent/state.py` defining `AgentState`.
    * *Affected Files:* `app/agent/tools.py`, `app/agent/state.py`.
    * *Dependencies:* `TSK-15`.
    * *Completion Criteria:* Tools return typed, structured JSON payloads directly from database/analysis engine.
    * *Verification:* Unit test executing each tool directly and asserting valid schema output.
    * *Subtasks:*
      - `SUB-57`: Define `AgentState` TypedDict.
      - `SUB-58`: Implement and decorate analysis tools.
      - `SUB-59`: Write tests in `tests/unit/test_agent_tools.py`.

#### Story 13: LangGraph Workflow & Evidence Grounding (`ST-13`)
* **Outcome:** Stateful agent graph executing intent classification -> tool execution -> evidence validation -> grounded response synthesis.
* **Dependencies:** `ST-12`.
* **Tasks:**
  * **Task 17: Build LangGraph Workflow Engine (`TSK-17`)**
    * *Instructions:* Create `app/agent/graph.py` compiling the workflow graph. Implement nodes for classification, tool calling, evidence sufficiency check, and synthesis. Add fallback for missing data. Expose via `POST /api/v1/agent/query`.
    * *Affected Files:* `app/agent/graph.py`, `app/agent/prompts.py`, `app/api/v1/router_agent.py`.
    * *Dependencies:* `TSK-16`.
    * *Completion Criteria:* Agent answers questions using tool evidence; refuses to invent missing data; passes ground truth evaluation.
    * *Verification:* Integration tests evaluating the 6 core business questions on sample data.
    * *Subtasks:*
      - `SUB-60`: Implement workflow nodes and edges with StateGraph.
      - `SUB-61`: Craft strict grounding prompt templates.
      - `SUB-62`: Connect LLM provider with fallback handling.
      - `SUB-63`: Implement `/agent/query` route.
      - `SUB-64`: Write tests in `tests/integration/test_agent_workflow.py`.

---

## Phase 8: Frontend Dashboard, Visualization & Local Acceptance (`PH-08`)

### Epic 8: Streamlit Owner Dashboard & UI (`EP-08`)
* **Purpose:** Deliver an intuitive, responsive Streamlit dashboard with KPI cards, blockage diagnostics, interactive graph visualization, and natural language chat.
* **Scope:** Streamlit app, PyVis visualizer, file upload interface, and chat component.
* **Prerequisites:** `EP-07`.
* **Stories:** `ST-14`, `ST-15`
* **Definition of Done:** Dashboard runs locally, communicates with FastAPI backend, visualizes graph cleanly, and handles chat interactions.

#### Story 14: Interactive Dashboard & Graph Explorer (`ST-14`)
* **Outcome:** Visual interface displaying business metrics, blockage tables, and interactive network graphs.
* **Dependencies:** `ST-13`.
* **Tasks:**
  * **Task 18: Build Dashboard Pages and Graph Viewer (`TSK-18`)**
    * *Instructions:* Create `frontend/app.py` and components:
      - KPI Summary Cards.
      - Cash Blockage Diagnostic Grid with severity indicators.
      - PyVis interactive graph visualization embedded in Streamlit iframe.
      - Ingestion / File Upload page with real-time validation error display.
    * *Affected Files:* `frontend/app.py`, `frontend/components/graph_view.py`, `frontend/components/kpi_cards.py`.
    * *Dependencies:* `TSK-17`.
    * *Completion Criteria:* UI renders real backend data, highlights blockages, and allows interactive graph node inspection.
    * *Verification:* Manual and automated UI verification.
    * *Subtasks:*
      - `SUB-65`: Implement Streamlit layout and API client.
      - `SUB-66`: Implement KPI cards and blockage table.
      - `SUB-67`: Implement PyVis graph generator with color coding.
      - `SUB-68`: Implement file upload component.

#### Story 15: Conversational Chat UI & Audit Inspection (`ST-15`)
* **Outcome:** Natural language chat console in Streamlit with expandable record citation views.
* **Dependencies:** `ST-14`.
* **Tasks:**
  * **Task 19: Build Agent Chat Interface (`TSK-19`)**
    * *Instructions:* Implement chat interface in Streamlit using `st.chat_input` and `st.chat_message`. Include collapsible expanders showing tool calls, cited record IDs, and data warnings.
    * *Affected Files:* `frontend/components/chat.py`.
    * *Dependencies:* `TSK-18`.
    * *Completion Criteria:* Chat interface sends queries to backend, streams or renders answers, and shows evidence citations.
    * *Verification:* Interactive test asking target questions.
    * *Subtasks:*
      - `SUB-69`: Implement chat message state and display.
      - `SUB-70`: Add evidence citation accordion.
      - `SUB-71`: Add quick-prompt buttons for common questions.

---

### Epic 9: System Verification, Documentation & Handover (`EP-09`)
* **Purpose:** Validate complete end-to-end functionality against all 6 project acceptance scenarios, verify local reproducibility, and finalize documentation.
* **Scope:** End-to-end regression tests, verification runs, local runbook, and final documentation alignment.
* **Prerequisites:** `EP-08`.
* **Stories:** `ST-16`
* **Definition of Done:** All acceptance scenarios verified with automated tests; local runbook tested; documentation complete.

#### Story 16: Acceptance Scenarios & Local Runbook (`ST-16`)
* **Outcome:** Comprehensive end-to-end test suite and verified step-by-step local execution instructions.
* **Dependencies:** `ST-15`.
* **Tasks:**
  * **Task 20: Implement End-to-End Acceptance Test Suite (`TSK-20`)**
    * *Instructions:* Create `tests/e2e/test_scenarios.py` verifying:
      - Scenario 1: Overdue customer invoice lifecycle and grounding.
      - Scenario 2: Stranded supplier advance detection.
      - Scenario 3: Upcoming obligation shortfall projection.
      - Scenario 4: Real data ingestion and idempotent re-import.
      - Scenario 5: Evidence-grounded agent query.
      - Scenario 6: Local reproducibility and health verification.
    * *Affected Files:* `tests/e2e/test_scenarios.py`.
    * *Dependencies:* `TSK-19`.
    * *Completion Criteria:* 100% test pass across all acceptance scenarios.
    * *Verification:* Run `pytest tests/e2e`.
    * *Subtasks:*
      - `SUB-72`: Implement Scenario 1 test.
      - `SUB-73`: Implement Scenario 2 test.
      - `SUB-74`: Implement Scenario 3 test.
      - `SUB-75`: Implement Scenario 4 test.
      - `SUB-76`: Implement Scenario 5 test.
      - `SUB-77`: Execute full test suite (`pytest`) and capture test logs.
  * **Task 21: Finalize Local Development Runbook & Handover (`TSK-21`)**
    * *Instructions:* Create `RUNBOOK.md` detailing exact prerequisites, local database startup, environment configuration, migration commands, application startup (`uvicorn` and `streamlit`), and troubleshooting.
    * *Affected Files:* `RUNBOOK.md`, `README.md`.
    * *Dependencies:* `TSK-20`.
    * *Completion Criteria:* Complete, unambiguous local reproduction instructions.
    * *Verification:* Walkthrough verification of commands.
    * *Subtasks:*
      - `SUB-78`: Document local PostgreSQL and Neo4j setup steps.
      - `SUB-79`: Document environment configuration and migrations.
      - `SUB-80`: Document backend and frontend startup commands.
      - `SUB-81`: Finalize documentation consistency check across all markdown files.
