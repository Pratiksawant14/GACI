"""
Integration Tests for FastAPI REST API Endpoints.
Verifies health probes, ledger file uploads, financial analysis endpoints,
graph sync, contagion tracing, and error handling middleware using TestClient.
"""

import io
import os
import uuid
from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.db.session import get_db
from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import SalesInvoice, FinancialObligation


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency yielding the test session."""
    application = create_app()

    def override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as c:
        yield c
    application.dependency_overrides.clear()


def test_health_and_readiness_endpoints(client):
    """Verifies liveness and readiness probe responses."""
    # Test root health
    res_health = client.get("/health")
    assert res_health.status_code == 200
    data_health = res_health.json()
    assert data_health["status"] == "healthy"
    assert "version" in data_health

    # Test v1 health
    res_v1_health = client.get("/api/v1/health")
    assert res_v1_health.status_code == 200
    assert res_v1_health.json()["status"] == "healthy"

    # Test readiness probe
    res_ready = client.get("/ready")
    assert res_ready.status_code == 200
    data_ready = res_ready.json()
    assert data_ready["database_connected"] is True
    assert data_ready["status"] in ("ready", "degraded")


def test_ingest_single_file_endpoint(client, db_session):
    """Verifies file upload and ingestion through POST /api/v1/ingest/upload."""
    csv_content = (
        "name,credit_limit,standard_payment_terms_days,customer_code\n"
        "Metro Retail Hub,100000.00,30,CUST-METRO\n"
        "City Mart Traders,50000.00,15,CUST-CITY\n"
    )
    files = [
        ("files", ("customers.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv"))
    ]

    response = client.post("/api/v1/ingest/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_files_processed"] == 1
    assert data["graph_synced"] is True
    assert len(data["reports"]) == 1
    report = data["reports"][0]
    assert report["table_name"] == "customers"
    assert report["valid_rows"] == 2
    assert report["error_rows"] == 0


def test_ingest_multi_file_endpoint(client, db_session):
    """Verifies uploading multiple ledger files simultaneously."""
    biz = Business(name="Multi Upload Test Biz", currency="INR")
    db_session.add(biz)
    db_session.commit()

    cust_csv = "name,credit_limit,standard_payment_terms_days\nOmega Retail,200000.00,30\n"
    supp_csv = "name,standard_lead_time_days\nPrime Distro,14\n"

    files = [
        ("files", ("customers.csv", io.BytesIO(cust_csv.encode("utf-8")), "text/csv")),
        ("files", ("suppliers.csv", io.BytesIO(supp_csv.encode("utf-8")), "text/csv")),
    ]

    response = client.post(f"/api/v1/ingest/upload?business_id={biz.id}", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_files_processed"] == 2
    assert len(data["reports"]) == 2


def test_analysis_endpoints(client, db_session):
    """Verifies cash-summary, blockages, aging-buckets, and cash-projection endpoints."""
    biz = Business(name="Apex Wholesale Test", currency="INR")
    db_session.add(biz)
    db_session.flush()

    bank = BankAccount(business_id=biz.id, account_name="Primary Current", account_type="BANK", current_balance=Decimal("250000.00"))
    cust = Customer(business_id=biz.id, name="Test Retailer", credit_limit=Decimal("500000.00"))
    db_session.add_all([bank, cust])
    db_session.flush()

    inv = SalesInvoice(
        business_id=biz.id,
        customer_id=cust.id,
        invoice_number="INV-API-001",
        issue_date=date(2026, 9, 1),
        due_date=date(2026, 9, 20),
        total_amount=Decimal("80000.00"),
        paid_amount=Decimal("0.00"),
        status="OVERDUE"
    )
    ob = FinancialObligation(
        business_id=biz.id,
        obligation_name="Machinery Loan EMI",
        category="LOAN_EMI",
        due_date=date(2026, 10, 28),
        amount=Decimal("50000.00"),
        status="SCHEDULED"
    )
    db_session.add_all([inv, ob])
    db_session.commit()

    # 1. Cash Summary
    res_summary = client.get(f"/api/v1/analysis/cash-summary?business_id={biz.id}&as_of=2026-10-23")
    assert res_summary.status_code == 200
    data_summary = res_summary.json()
    assert Decimal(str(data_summary["liquid_cash"])) == Decimal("250000.00")
    assert Decimal(str(data_summary["total_overdue_receivables"])) == Decimal("80000.00")
    assert Decimal(str(data_summary["upcoming_obligations_15d"])) == Decimal("50000.00")

    # 2. Blockages
    res_blk = client.get(f"/api/v1/analysis/blockages?business_id={biz.id}&as_of=2026-10-23")
    assert res_blk.status_code == 200
    data_blk = res_blk.json()
    assert len(data_blk) == 1
    assert data_blk[0]["entity_name"] == "Test Retailer"
    assert Decimal(str(data_blk[0]["amount"])) == Decimal("80000.00")

    # 3. Aging Buckets
    res_aging = client.get(f"/api/v1/analysis/aging-buckets?business_id={biz.id}&as_of=2026-10-23")
    assert res_aging.status_code == 200
    data_aging = res_aging.json()
    assert len(data_aging) == 4
    bucket_map = {b["bucket"]: Decimal(str(b["total_amount"])) for b in data_aging}
    assert bucket_map["31-60 days"] == Decimal("80000.00")

    # 4. Cash Projection
    res_proj = client.get(f"/api/v1/analysis/cash-projection?business_id={biz.id}&as_of=2026-10-23&horizon_days=15")
    assert res_proj.status_code == 200
    data_proj = res_proj.json()
    assert data_proj["forecast_horizon_days"] == 15
    assert len(data_proj["daily_forecasts"]) >= 15
    assert Decimal(str(data_proj["starting_liquid_cash"])) == Decimal("250000.00")


def test_graph_endpoints(client, db_session):
    """Verifies graph synchronization, subgraph extraction, contagion paths, and concentration endpoints."""
    biz = Business(name="Graph API Test Biz", currency="INR")
    db_session.add(biz)
    db_session.flush()

    cust = Customer(business_id=biz.id, name="Contagion Customer")
    db_session.add(cust)
    db_session.flush()

    inv = SalesInvoice(
        business_id=biz.id,
        customer_id=cust.id,
        invoice_number="INV-CONTAGION-01",
        issue_date=date(2026, 9, 1),
        due_date=date(2026, 9, 15),
        total_amount=Decimal("120000.00"),
        paid_amount=Decimal("0.00"),
        status="OVERDUE"
    )
    ob = FinancialObligation(
        business_id=biz.id,
        obligation_name="Upcoming Tax GST",
        category="TAX",
        due_date=date(2026, 10, 27),
        amount=Decimal("75000.00"),
        status="SCHEDULED"
    )
    db_session.add_all([inv, ob])
    db_session.commit()

    # 1. Graph Sync
    res_sync = client.post(f"/api/v1/graph/sync?business_id={biz.id}")
    assert res_sync.status_code == 200
    data_sync = res_sync.json()
    assert data_sync["status"] == "success"
    assert data_sync["synced_nodes"] >= 4

    # 2. Subgraph
    res_subgraph = client.get(f"/api/v1/graph/subgraph?business_id={biz.id}")
    assert res_subgraph.status_code == 200
    data_subgraph = res_subgraph.json()
    assert "nodes" in data_subgraph
    assert "edges" in data_subgraph
    assert len(data_subgraph["nodes"]) >= 4

    # 3. Contagion Paths
    res_paths = client.get(f"/api/v1/graph/contagion-paths?business_id={biz.id}&as_of=2026-10-23&horizon_days=15")
    assert res_paths.status_code == 200
    paths = res_paths.json()
    assert len(paths) >= 1
    assert paths[0]["customer_name"] == "Contagion Customer"
    assert paths[0]["obligation_name"] == "Upcoming Tax GST"

    # 4. Concentrations
    res_conc = client.get(f"/api/v1/graph/concentrations?business_id={biz.id}")
    assert res_conc.status_code == 200
    data_conc = res_conc.json()
    assert isinstance(data_conc, list)
    assert len(data_conc) >= 1
    assert data_conc[0]["customer_name"] == "Contagion Customer"


def test_api_error_handling(client):
    """Verifies standardized error responses for 404 and 422 conditions."""
    fake_id = uuid.uuid4()
    # 404 for non-existent business
    res_404 = client.get(f"/api/v1/analysis/cash-summary?business_id={fake_id}")
    assert res_404.status_code == 404
    err_404 = res_404.json()
    assert "error" in err_404
    assert err_404["error"]["code"] == "HTTP_404"

    # 422 for invalid date format
    res_422 = client.get("/api/v1/analysis/cash-summary?as_of=not-a-date")
    assert res_422.status_code == 422
    err_422 = res_422.json()
    assert "error" in err_422
    assert err_422["error"]["code"] == "VALIDATION_ERROR"
