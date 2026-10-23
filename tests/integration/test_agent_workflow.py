"""
Integration Tests for LangGraph Agent Workflow and API Endpoint (TSK-17).
Verifies multi-stage state transitions, citation extraction,
and grounded question answering via POST /api/v1/agent/query.
"""

import uuid
from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.db.session import get_db
from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import SalesInvoice, SupplierAdvance, FinancialObligation
from app.agent.graph import CashFlowAgentWorkflow


@pytest.fixture
def client(db_session):
    application = create_app()

    def override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as c:
        yield c
    application.dependency_overrides.clear()


def test_agent_workflow_execution(db_session):
    """Verifies end-to-end LangGraph state transitions and citation compilation."""
    biz = Business(name="Workflow Test Enterprise", currency="INR")
    db_session.add(biz)
    db_session.flush()

    bank = BankAccount(business_id=biz.id, account_name="Main Current", current_balance=Decimal("300000.00"))
    cust = Customer(business_id=biz.id, name="Royal Supermarkets")
    supp = Supplier(business_id=biz.id, name="National Mills")
    db_session.add_all([bank, cust, supp])
    db_session.flush()

    inv = SalesInvoice(
        business_id=biz.id,
        customer_id=cust.id,
        invoice_number="INV-WF-100",
        issue_date=date(2026, 9, 10),
        due_date=date(2026, 9, 30),
        total_amount=Decimal("175000.00"),
        paid_amount=Decimal("25000.00"),
        status="OVERDUE"
    )
    adv = SupplierAdvance(
        business_id=biz.id,
        supplier_id=supp.id,
        bank_account_id=bank.id,
        advance_reference="ADV-WF-200",
        disbursement_date=date(2026, 9, 1),
        expected_delivery_date=date(2026, 9, 15),
        advance_amount=Decimal("50000.00"),
        fulfilled_amount=Decimal("0.00"),
        status="DISBURSED"
    )
    ob = FinancialObligation(
        business_id=biz.id,
        bank_account_id=bank.id,
        obligation_name="Monthly GST Liability",
        category="TAX",
        due_date=date(2026, 10, 25),
        amount=Decimal("120000.00"),
        status="SCHEDULED"
    )
    db_session.add_all([inv, adv, ob])
    db_session.commit()

    workflow = CashFlowAgentWorkflow(db=db_session)
    state = workflow.execute(
        query="Where is our cash stuck and how does it affect our upcoming GST payment?",
        business_id=biz.id,
        as_of=date(2026, 10, 23)
    )

    assert state["intent"] in ("contagion", "blockage", "comprehensive")
    assert state["provider_used"] is not None
    assert len(state["citations"]) >= 2

    citation_identifiers = [c["identifier"] for c in state["citations"]]
    assert any("INV-WF-100" in cid for cid in citation_identifiers)
    assert any("ADV-WF-200" in cid for cid in citation_identifiers)

    # Verify that the generated answer cites the specific entities
    answer = state["final_response"]
    assert "Royal Supermarkets" in answer or "150,000" in answer or "175,000" in answer
    assert "₹" in answer


def test_agent_query_api_endpoint(client, db_session):
    """Verifies POST /api/v1/agent/query endpoint returns structured response with citations."""
    biz = Business(name="Agent API Test Co", currency="INR")
    db_session.add(biz)
    db_session.flush()

    cust = Customer(business_id=biz.id, name="Urban Mart")
    db_session.add(cust)
    db_session.flush()

    inv = SalesInvoice(
        business_id=biz.id,
        customer_id=cust.id,
        invoice_number="INV-API-Q1",
        issue_date=date(2026, 9, 1),
        due_date=date(2026, 9, 25),
        total_amount=Decimal("95000.00"),
        paid_amount=Decimal("0.00"),
        status="OVERDUE"
    )
    db_session.add(inv)
    db_session.commit()

    payload = {
        "query": "Which customers have overdue payments?",
        "business_id": str(biz.id),
        "as_of": "2026-10-23"
    }

    response = client.post("/api/v1/agent/query", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["query"] == payload["query"]
    assert "answer" in data
    assert len(data["answer"]) > 10
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["counterparty"] == "Urban Mart"
    assert data["citations"][0]["amount"] == 95000.00
    assert "evidence" in data
    assert "provider_used" in data
