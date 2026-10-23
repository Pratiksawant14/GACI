"""
End-to-End Acceptance Tests for Wholesale MSME Decision Support (TSK-20).
Validates the complete 6-stage lifecycle using realistic distributor CSV datasets:
- Scenario A: Realistic wholesale data ingestion from CSV
- Scenario B: Correct liquid cash balance calculation
- Scenario C: Overdue invoice detection and aging bucket classification
- Scenario D: Stranded advance detection against expected delivery dates
- Scenario E: Graph contagion tracing from customer delay to loan/tax default
- Scenario F: Agent explainability citing exact canonical records without hallucination
"""

import os
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import SalesInvoice, SupplierAdvance, FinancialObligation
from app.services.ingestion_service import IngestionService
from app.analysis.cash_engine import CashEngine
from app.graph.contagion import GraphContagionEngine
from app.agent.graph import CashFlowAgentWorkflow


SAMPLE_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "samples"))


@pytest.fixture
def wholesale_distributor_dataset(db_session: Session):
    """Ingests the full realistic sample dataset into an isolated in-memory test database."""
    biz = Business(name="Apex Wholesale Distributors", currency="INR")
    db_session.add(biz)
    db_session.commit()
    db_session.refresh(biz)

    service = IngestionService(db_session)
    files_order = [
        ("customers.csv", "customers"),
        ("suppliers.csv", "suppliers"),
        ("bank_accounts.csv", "bank_accounts"),
        ("invoices.csv", "invoices"),
        ("payments.csv", "payments"),
        ("advances.csv", "advances"),
        ("deliveries.csv", "deliveries"),
        ("obligations.csv", "obligations"),
    ]

    reports = []
    for fname, ttype in files_order:
        fpath = os.path.join(SAMPLE_DATA_DIR, fname)
        assert os.path.exists(fpath), f"Sample file missing: {fpath}"
        with open(fpath, "rb") as f:
            content = f.read()
        rep = service.ingest_table(
            business_id=biz.id,
            file_content=content,
            table_type=ttype,
            filename=fname
        )
        reports.append(rep)

    return {"business": biz, "reports": reports}


def test_scenario_a_data_ingestion(wholesale_distributor_dataset):
    """Scenario A: Verifies realistic wholesale data ingestion from CSV."""
    reports = wholesale_distributor_dataset["reports"]
    assert len(reports) == 8
    total_valid = sum(r.valid_rows for r in reports)
    total_errors = sum(r.error_rows for r in reports)
    assert total_valid >= 30
    assert total_errors == 0


def test_scenario_b_liquid_cash_calculation(db_session, wholesale_distributor_dataset):
    """Scenario B: Correct liquid cash balance calculation across bank accounts and cash tills."""
    biz = wholesale_distributor_dataset["business"]
    engine = CashEngine(db_session)
    liquid = engine.calculate_liquid_cash(biz.id)
    # HDFC Main Current (175,000) + Warehouse Petty Cash (25,000) + SBI Trade (85,000) = 285,000.00
    assert liquid == Decimal("285000.00")


def test_scenario_c_overdue_invoice_and_aging_buckets(db_session, wholesale_distributor_dataset):
    """Scenario C: Overdue invoice detection and aging bucket classification."""
    biz = wholesale_distributor_dataset["business"]
    engine = CashEngine(db_session)
    as_of = date(2026, 10, 23)

    blockages = engine.calculate_overdue_receivables(biz.id, as_of=as_of)
    assert len(blockages) >= 3

    # Check Metro Supermarkets overdue invoice (INV-2026-101)
    metro_blk = next((b for b in blockages if "INV-2026-101" in b.blockage_id), None)
    assert metro_blk is not None
    assert metro_blk.entity_name == "Metro Supermarkets"
    assert metro_blk.amount == Decimal("180000.00")
    assert metro_blk.days_overdue > 20

    # Aging buckets
    buckets = engine.get_aging_buckets(blockages)
    assert len(buckets) == 4
    bucket_dict = {b.bucket: b.total_amount for b in buckets}
    assert bucket_dict["1-30 days"] > Decimal("0.00")
    assert bucket_dict["31-60 days"] > Decimal("0.00")


def test_scenario_d_stranded_advance_detection(db_session, wholesale_distributor_dataset):
    """Scenario D: Stranded advance detection against expected delivery dates."""
    biz = wholesale_distributor_dataset["business"]
    engine = CashEngine(db_session)
    as_of = date(2026, 10, 23)

    advances = engine.calculate_stranded_advances(biz.id, as_of=as_of)
    assert len(advances) >= 1

    # Check Sunrise Agro Industries advance ADV-2026-001 (disbursed 2026-09-10, expected 2026-09-25, ₹20,000 net unfulfilled after delivery)
    stranded = next((a for a in advances if "ADV-2026-001" in a.blockage_id), None)
    assert stranded is not None
    assert stranded.entity_name == "Sunrise Agro Industries"
    assert stranded.amount == Decimal("20000.00")
    assert stranded.days_overdue > 20


def test_scenario_e_graph_contagion_path_tracing(db_session, wholesale_distributor_dataset):
    """Scenario E: Graph contagion tracing from customer delay to loan/tax default."""
    biz = wholesale_distributor_dataset["business"]
    contagion_engine = GraphContagionEngine(db_session)
    as_of = date(2026, 10, 23)

    paths = contagion_engine.trace_receivable_to_obligation_paths(biz.id, as_of=as_of, horizon_days=15)
    assert len(paths) >= 1

    # Check causal links
    first_path = paths[0]
    assert "customer_name" in first_path
    assert "obligation_name" in first_path
    assert "causal_link" in first_path
    assert first_path["obligation_name"] in (
        "Staff Payroll October",
        "Quarterly GST Settlement",
        "Warehouse Mortgage Loan EMI",
        "Warehouse Lease Rent"
    )


def test_scenario_f_agent_explainability_zero_hallucination(db_session, wholesale_distributor_dataset):
    """Scenario F: Agent explainability citing exact canonical records without hallucination."""
    biz = wholesale_distributor_dataset["business"]
    workflow = CashFlowAgentWorkflow(db=db_session)
    as_of = date(2026, 10, 23)

    query = "Where is my cash stuck and will it cause a default on my upcoming GST or loan EMI?"
    state = workflow.execute(query=query, business_id=biz.id, as_of=as_of)

    # 1. State integrity
    assert state["intent"] in ("contagion", "blockage", "comprehensive")
    assert len(state["citations"]) >= 3

    # 2. Citations must contain exact canonical identifiers from dataset
    identifiers = [c["identifier"] for c in state["citations"]]
    assert any("INV-2026-101" in i for i in identifiers)
    assert any("ADV-2026-001" in i for i in identifiers)

    # 3. Final response text must explicitly mention real entities and amounts
    response_text = state["final_response"]
    assert "Metro Supermarkets" in response_text or "Sunrise Agro" in response_text or "285,000" in response_text
    assert "₹" in response_text
