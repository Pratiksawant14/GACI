"""
Integration tests for Graph Projection Service (TSK-09).
Verifies mapping of relational database records to graph nodes, edges, and topology.
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import (
    SalesInvoice,
    Payment,
    PaymentAllocation,
    SupplierAdvance,
    Delivery,
    FinancialObligation
)
from app.graph.client import Neo4jClient
from app.services.projection_service import ProjectionService


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


def test_projection_service_sync_and_networkx(session: Session):
    # Setup test relational records
    biz = Business(name="National Wholesalers")
    session.add(biz)
    session.flush()

    cust = Customer(business_id=biz.id, name="Royal Mart", credit_limit=Decimal("500000.00"))
    sup = Supplier(business_id=biz.id, name="Delta Textiles")
    bank = BankAccount(business_id=biz.id, account_name="Current Account", current_balance=Decimal("200000.00"))
    session.add_all([cust, sup, bank])
    session.flush()

    inv = SalesInvoice(
        business_id=biz.id,
        customer_id=cust.id,
        invoice_number="INV-2026-901",
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 20),
        total_amount=Decimal("120000.00"),
        paid_amount=Decimal("40000.00"),
        status="PARTIAL"
    )
    pmt = Payment(
        business_id=biz.id,
        customer_id=cust.id,
        bank_account_id=bank.id,
        payment_reference="PMT-501",
        payment_date=date(2026, 10, 10),
        amount=Decimal("40000.00"),
        status="CLEARED"
    )
    session.add_all([inv, pmt])
    session.flush()

    alloc = PaymentAllocation(
        payment_id=pmt.id,
        invoice_id=inv.id,
        allocated_amount=Decimal("40000.00")
    )
    adv = SupplierAdvance(
        business_id=biz.id,
        supplier_id=sup.id,
        bank_account_id=bank.id,
        advance_reference="ADV-101",
        disbursement_date=date(2026, 10, 5),
        expected_delivery_date=date(2026, 10, 15),
        advance_amount=Decimal("80000.00"),
        fulfilled_amount=Decimal("30000.00"),
        status="PARTIAL_DELIVERED"
    )
    session.add_all([alloc, adv])
    session.flush()

    deliv = Delivery(
        business_id=biz.id,
        supplier_id=sup.id,
        advance_id=adv.id,
        delivery_reference="DEL-301",
        delivery_date=date(2026, 10, 12),
        delivered_value=Decimal("30000.00")
    )
    ob = FinancialObligation(
        business_id=biz.id,
        bank_account_id=bank.id,
        obligation_name="Equipment Lease",
        category="RENT",
        due_date=date(2026, 10, 25),
        amount=Decimal("25000.00"),
        status="SCHEDULED"
    )
    session.add_all([deliv, ob])
    session.commit()

    # Mock Neo4j client to verify queries dispatched
    mock_neo4j = MagicMock(spec=Neo4jClient)
    mock_neo4j.verify_connectivity.return_value = True

    service = ProjectionService(session=session, graph_client=mock_neo4j)
    counts = service.sync_all(business_id=biz.id)

    # Verify counts
    assert counts["businesses"] == 1
    assert counts["customers"] == 1
    assert counts["suppliers"] == 1
    assert counts["bank_accounts"] == 1
    assert counts["invoices"] == 1
    assert counts["payments"] == 1
    assert counts["advances"] == 1
    assert counts["deliveries"] == 1
    assert counts["obligations"] == 1

    # Verify Cypher write was invoked for all entities
    assert mock_neo4j.execute_write.call_count >= 9

    # Verify in-memory NetworkX projection graph
    G = service.build_networkx_graph(business_id=biz.id)
    assert G.number_of_nodes() == 9
    assert G.has_edge(f"customer_{cust.id}", f"invoice_{inv.id}")
    assert G.has_edge(f"payment_{pmt.id}", f"invoice_{inv.id}")
    assert G.has_edge(f"payment_{pmt.id}", f"bank_{bank.id}")
    assert G.has_edge(f"business_{biz.id}", f"advance_{adv.id}")
    assert G.has_edge(f"advance_{adv.id}", f"supplier_{sup.id}")
    assert G.has_edge(f"delivery_{deliv.id}", f"advance_{adv.id}")
    assert G.has_edge(f"business_{biz.id}", f"obligation_{ob.id}")
    assert G.has_edge(f"obligation_{ob.id}", f"bank_{bank.id}")
