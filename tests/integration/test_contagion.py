"""
Integration tests for Graph Contagion Engine (TSK-14).
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import SalesInvoice, FinancialObligation
from app.graph.client import Neo4jClient
from app.graph.contagion import GraphContagionEngine


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


def test_contagion_path_tracing(session: Session):
    biz = Business(name="Apex Wholesale")
    session.add(biz)
    session.flush()

    cust1 = Customer(business_id=biz.id, name="Metro Mart")
    cust2 = Customer(business_id=biz.id, name="City Grocers")
    bank = BankAccount(business_id=biz.id, account_name="Main Current", current_balance=Decimal("20000.00"))
    session.add_all([cust1, cust2, bank])
    session.flush()

    # Overdue invoice from Metro Mart
    inv = SalesInvoice(
        business_id=biz.id, customer_id=cust1.id, invoice_number="INV-001",
        issue_date=date(2026, 9, 1), due_date=date(2026, 9, 30),
        total_amount=Decimal("150000.00"), paid_amount=Decimal("0.00"), status="OVERDUE"
    )

    # Impending loan EMI on 2026-10-25
    ob = FinancialObligation(
        business_id=biz.id, bank_account_id=bank.id,
        obligation_name="Warehouse Loan EMI", category="LOAN_EMI",
        due_date=date(2026, 10, 25), amount=Decimal("120000.00"), status="SCHEDULED"
    )
    session.add_all([inv, ob])
    session.commit()

    mock_neo4j = MagicMock(spec=Neo4jClient)
    mock_neo4j.verify_connectivity.return_value = False  # test relational / NetworkX path

    engine = GraphContagionEngine(session, mock_neo4j)
    paths = engine.trace_receivable_to_obligation_paths(biz.id, as_of=date(2026, 10, 15), horizon_days=15)

    assert len(paths) == 1
    p = paths[0]
    assert p["customer_name"] == "Metro Mart"
    assert p["invoice_number"] == "INV-001"
    assert p["obligation_name"] == "Warehouse Loan EMI"
    assert "contributes directly to cash shortfall" in p["causal_link"]


def test_counterparty_concentration_risk(session: Session):
    biz = Business(name="Apex Wholesale")
    session.add(biz)
    session.flush()

    c1 = Customer(business_id=biz.id, name="Big Buyer")
    c2 = Customer(business_id=biz.id, name="Small Buyer")
    session.add_all([c1, c2])
    session.flush()

    # Big buyer owes 80,000 (80%)
    inv1 = SalesInvoice(
        business_id=biz.id, customer_id=c1.id, invoice_number="INV-BIG",
        issue_date=date(2026, 9, 1), due_date=date(2026, 9, 30),
        total_amount=Decimal("80000.00"), paid_amount=Decimal("0.00"), status="OVERDUE"
    )
    # Small buyer owes 20,000 (20%)
    inv2 = SalesInvoice(
        business_id=biz.id, customer_id=c2.id, invoice_number="INV-SML",
        issue_date=date(2026, 9, 1), due_date=date(2026, 9, 30),
        total_amount=Decimal("20000.00"), paid_amount=Decimal("0.00"), status="OVERDUE"
    )
    session.add_all([inv1, inv2])
    session.commit()

    engine = GraphContagionEngine(session, None)
    concentrations = engine.find_top_counterparty_concentrations(biz.id)

    assert len(concentrations) == 2
    assert concentrations[0]["customer_name"] == "Big Buyer"
    assert concentrations[0]["concentration_percentage"] == 80.0
    assert concentrations[1]["customer_name"] == "Small Buyer"
    assert concentrations[1]["concentration_percentage"] == 20.0


def test_entity_subgraph_extraction(session: Session):
    biz = Business(name="Apex Wholesale")
    session.add(biz)
    session.flush()

    cust = Customer(business_id=biz.id, name="Metro Mart")
    bank = BankAccount(business_id=biz.id, account_name="Current Account", current_balance=Decimal("50000.00"))
    session.add_all([cust, bank])
    session.flush()

    inv = SalesInvoice(
        business_id=biz.id, customer_id=cust.id, invoice_number="INV-101",
        issue_date=date(2026, 10, 1), due_date=date(2026, 10, 31),
        total_amount=Decimal("40000.00"), paid_amount=Decimal("0.00"), status="ISSUED"
    )
    session.add(inv)
    session.commit()

    engine = GraphContagionEngine(session, None)
    subgraph = engine.get_entity_subgraph(biz.id)

    assert subgraph["total_nodes"] >= 4
    assert subgraph["total_edges"] >= 1
    # Check node types present
    node_types = {n["type"] for n in subgraph["nodes"]}
    assert "Business" in node_types
    assert "Customer" in node_types
    assert "Invoice" in node_types
    assert "BankAccount" in node_types
