"""
Integration tests for Ingestion Service (TSK-11).
Verifies CSV parsing, row validation, deduplication, and transactional audit persistence.
"""

from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import SalesInvoice, Payment, SupplierAdvance, Delivery, FinancialObligation, IngestionLog
from app.graph.client import Neo4jClient
from app.services.ingestion_service import IngestionService


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


def test_full_sample_ingestion_flow(session: Session):
    # Setup business
    biz = Business(name="Apex Wholesale Traders", currency="INR")
    session.add(biz)
    session.commit()

    mock_neo4j = MagicMock(spec=Neo4jClient)
    mock_neo4j.verify_connectivity.return_value = False  # Offline mode test

    ingest_svc = IngestionService(session, mock_neo4j)

    # 1. Ingest Bank Accounts
    with open("data/samples/bank_accounts.csv", "rb") as f:
        rep_bank = ingest_svc.ingest_table(biz.id, f.read(), "bank_accounts", "bank_accounts.csv")
    assert rep_bank.status == "SUCCESS"
    assert rep_bank.valid_rows == 3

    # 2. Ingest Customers
    with open("data/samples/customers.csv", "rb") as f:
        rep_cust = ingest_svc.ingest_table(biz.id, f.read(), "customers", "customers.csv")
    assert rep_cust.status == "SUCCESS"
    assert rep_cust.valid_rows == 5

    # 3. Ingest Suppliers
    with open("data/samples/suppliers.csv", "rb") as f:
        rep_sup = ingest_svc.ingest_table(biz.id, f.read(), "suppliers", "suppliers.csv")
    assert rep_sup.status == "SUCCESS"
    assert rep_sup.valid_rows == 3

    # 4. Ingest Invoices
    with open("data/samples/invoices.csv", "rb") as f:
        rep_inv = ingest_svc.ingest_table(biz.id, f.read(), "invoices", "invoices.csv")
    assert rep_inv.status == "SUCCESS"
    assert rep_inv.valid_rows == 8

    # 5. Ingest Payments
    with open("data/samples/payments.csv", "rb") as f:
        rep_pmt = ingest_svc.ingest_table(biz.id, f.read(), "payments", "payments.csv")
    assert rep_pmt.status == "SUCCESS"
    assert rep_pmt.valid_rows == 4

    # 6. Ingest Advances
    with open("data/samples/advances.csv", "rb") as f:
        rep_adv = ingest_svc.ingest_table(biz.id, f.read(), "advances", "advances.csv")
    assert rep_adv.status == "SUCCESS"
    assert rep_adv.valid_rows == 3

    # 7. Ingest Deliveries
    with open("data/samples/deliveries.csv", "rb") as f:
        rep_deliv = ingest_svc.ingest_table(biz.id, f.read(), "deliveries", "deliveries.csv")
    assert rep_deliv.status == "SUCCESS"
    assert rep_deliv.valid_rows == 2

    # 8. Ingest Obligations
    with open("data/samples/obligations.csv", "rb") as f:
        rep_ob = ingest_svc.ingest_table(biz.id, f.read(), "obligations", "obligations.csv")
    assert rep_ob.status == "SUCCESS"
    assert rep_ob.valid_rows == 4

    # Verify counts in database
    assert len(session.scalars(select(Customer)).all()) == 5
    assert len(session.scalars(select(Supplier)).all()) == 3
    assert len(session.scalars(select(SalesInvoice)).all()) == 8
    assert len(session.scalars(select(Payment)).all()) == 4
    assert len(session.scalars(select(SupplierAdvance)).all()) == 3
    assert len(session.scalars(select(Delivery)).all()) == 2
    assert len(session.scalars(select(FinancialObligation)).all()) == 4
    assert len(session.scalars(select(IngestionLog)).all()) == 8


def test_idempotent_reingestion(session: Session):
    biz = Business(name="Apex Wholesale")
    session.add(biz)
    session.commit()

    mock_neo4j = MagicMock(spec=Neo4jClient)
    mock_neo4j.verify_connectivity.return_value = False
    ingest_svc = IngestionService(session, mock_neo4j)

    # First ingest
    with open("data/samples/customers.csv", "rb") as f:
        content = f.read()
    rep1 = ingest_svc.ingest_table(biz.id, content, "customers", "customers.csv")
    assert rep1.valid_rows == 5
    count1 = len(session.scalars(select(Customer)).all())

    # Re-ingest exact same file
    rep2 = ingest_svc.ingest_table(biz.id, content, "customers", "customers.csv")
    assert rep2.valid_rows == 5
    count2 = len(session.scalars(select(Customer)).all())

    # Count must remain exactly 5 (zero duplicate customer rows inserted)
    assert count1 == count2 == 5


def test_malformed_csv_error_reporting(session: Session):
    biz = Business(name="Apex Wholesale")
    session.add(biz)
    session.commit()

    mock_neo4j = MagicMock(spec=Neo4jClient)
    ingest_svc = IngestionService(session, mock_neo4j)

    malformed_csv = (
        "invoice_number,customer_name,issue_date,due_date,total_amount,paid_amount,status\n"
        "INV-BAD-1,Good Mart,2026-10-20,2026-10-10,50000.00,0.00,ISSUED\n"  # Invalid date order
        "INV-GOOD-1,Good Mart,2026-10-01,2026-10-30,70000.00,0.00,ISSUED\n"   # Valid
        "INV-BAD-2,Good Mart,2026-10-05,2026-10-25,-1000.00,0.00,ISSUED\n"     # Negative amount
    )

    report = ingest_svc.ingest_table(biz.id, malformed_csv.encode("utf-8"), "invoices", "bad_invoices.csv")
    assert report.status == "PARTIAL"
    assert report.total_rows == 3
    assert report.valid_rows == 1
    assert report.error_rows == 2
    assert len(report.errors) == 2
    assert report.errors[0].row_number == 1
    assert report.errors[1].row_number == 3
