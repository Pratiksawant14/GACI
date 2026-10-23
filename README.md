# Graph-Based Agentic Cash-Flow Intelligence System for Wholesale MSMEs

An agentic, time-aware decision-support platform designed for wholesale distributors and MSMEs. The system tracks working capital, detects and quantifies cash blockages (overdue accounts receivable, unfulfilled supplier advances, dishonored cheques, upcoming payment shortfalls), traces contagion paths through a temporal business graph, and explains findings with evidence-grounded reasoning.

## Architecture Highlights
* **Authoritative Canonical Ledger:** PostgreSQL (via SQLAlchemy 2.0+ & Alembic).
* **Temporal Business Graph Projection:** Neo4j (via official Neo4j Python Driver & parameterized Cypher).
* **Deterministic Analysis Engine:** Pure Python arithmetic (`Decimal`) computing A/R aging, unfulfilled advances, and liquidity projections.
* **Agent Orchestrator:** LangGraph state machine coordinating intent classification, tool invocation, evidence verification, and grounded answer synthesis.
* **Backend API:** FastAPI RESTful endpoints.
* **Frontend:** Streamlit interactive dashboard with PyVis graph visualization.

## Documentation Baseline
* [PROJECT_SOURCE.md](file:///d:/Sem-5/Deep%20Learning/Course_project/PROJECT_SOURCE.md): Stable system specification and architectural blueprints.
* [PROJECT_ROADMAP.md](file:///d:/Sem-5/Deep%20Learning/Course_project/PROJECT_ROADMAP.md): Complete hierarchical implementation plan.
* [IMPLEMENTATION_STATUS.md](file:///d:/Sem-5/Deep%20Learning/Course_project/IMPLEMENTATION_STATUS.md): Living engineering record and progress tracking.
