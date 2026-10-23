"""
Integration tests for database repositories and session management (TSK-07).
Verifies repository operations, query methods, and transaction rollback.
"""

import uuid
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import SalesInvoice, Payment, SupplierAdvance, FinancialObligation
from app.db.session import transactional
from app.db.repositories.party_repo import BusinessRepository, CustomerRepository, SupplierRepository
from app.db.repositories.finance_repo import InvoiceRepository, PaymentRepository, AdvanceRepository, ObligationRepository


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


def test_repositories_crud(session: Session):
    biz_repo = BusinessRepository(session)
    cust_repo = CustomerRepository(session)
    inv_repo = InvoiceRepository(session)

    # 1. Create Business
    biz = Business(name="Zenith Wholesalers", currency="INR")
    biz_repo.create(biz)
    assert biz_repo.get_by_id(biz.id) is not None

    # 2. Create Customer
    cust = Customer(business_id=biz.id, name="Prime Mart", credit_limit=Decimal("300000.00"))
    cust_repo.create(cust)
    assert cust_repo.get_by_name(biz.id, "Prime Mart") is not None

    # 3. Create Overdue Invoice
    inv1 = SalesInvoice(
        business_id=biz.id,
        customer_id=cust.id,
        invoice_number="INV-101",
        issue_date=date(2026, 9, 1),
        due_date=date(2026, 9, 30),
        total_amount=Decimal("50000.00"),
        paid_amount=Decimal("0.00"),
        status="OVERDUE"
    )
    # Not overdue yet invoice
    inv2 = SalesInvoice(
        business_id=biz.id,
        customer_id=cust.id,
        invoice_number="INV-102",
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 31),
        total_amount=Decimal("30000.00"),
        paid_amount=Decimal("0.00"),
        status="ISSUED"
    )
    inv_repo.create(inv1)
    inv_repo.create(inv2)

    # Query overdue as of 2026-10-15
    overdue = inv_repo.get_overdue_invoices(biz.id, as_of=date(2026, 10, 15))
    assert len(overdue) == 1
    assert overdue[0].invoice_number == "INV-101"


def test_advance_and_obligation_repositories(session: Session):
    biz = Business(name="Zenith Traders")
    session.add(biz)
    session.flush()

    sup = Supplier(business_id=biz.id, name="Agro Mills")
    bank = BankAccount(business_id=biz.id, account_name="Main Bank", current_balance=Decimal("150000.00"))
    session.add_all([sup, bank])
    session.flush()

    adv_repo = AdvanceRepository(session)
    ob_repo = ObligationRepository(session)

    # Stranded advance
    adv = SupplierAdvance(
        business_id=biz.id,
        supplier_id=sup.id,
        bank_account_id=bank.id,
        advance_reference="ADV-001",
        disbursement_date=date(2026, 9, 15),
        expected_delivery_date=date(2026, 10, 1),
        advance_amount=Decimal("60000.00"),
        fulfilled_amount=Decimal("10000.00"),
        status="PARTIAL_DELIVERED"
    )
    adv_repo.create(adv)

    stranded = adv_repo.get_stranded_advances(biz.id, as_of=date(2026, 10, 15))
    assert len(stranded) == 1
    assert stranded[0].advance_reference == "ADV-001"
    assert stranded[0].unfulfilled_balance == Decimal("50000.00")

    # Upcoming obligation
    ob = FinancialObligation(
        business_id=biz.id,
        bank_account_id=bank.id,
        obligation_name="Quarterly GST",
        category="TAX",
        due_date=date(2026, 10, 20),
        amount=Decimal("45000.00"),
        status="SCHEDULED"
    )
    ob_repo.create(ob)

    upcoming = ob_repo.get_upcoming_obligations(
        biz.id,
        start_date=date(2026, 10, 1),
        end_date=date(2026, 10, 31)
    )
    assert len(upcoming) == 1
    assert upcoming[0].obligation_name == "Quarterly GST"


def test_transactional_rollback(session: Session):
    biz_repo = BusinessRepository(session)
    initial_count = len(biz_repo.get_all())

    with pytest.raises(ValueError):
        with transactional(session):
            biz = Business(name="Temporary Business")
            biz_repo.create(biz)
            raise ValueError("Deliberate failure to test rollback")

    final_count = len(biz_repo.get_all())
    assert final_count == initial_count
