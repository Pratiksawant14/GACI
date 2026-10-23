"""
Unit tests for canonical database models (TSK-05).
Verifies model schemas, relationships, constraints, and balance calculations.
"""

import uuid
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
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


@pytest.fixture
def db_session():
    """In-memory SQLite engine for fast model schema verification."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)


def test_business_and_party_models(db_session: Session):
    # Create business
    biz = Business(
        name="Apex Wholesale Traders",
        currency="INR"
    )
    db_session.add(biz)
    db_session.flush()

    assert biz.id is not None
    assert biz.name == "Apex Wholesale Traders"

    # Create customer
    cust = Customer(
        business_id=biz.id,
        name="Metro Retail Mart",
        credit_limit=Decimal("500000.00"),
        standard_payment_terms_days=30
    )
    db_session.add(cust)
    db_session.flush()

    assert cust.id is not None
    assert cust.business_id == biz.id
    assert cust.credit_limit == Decimal("500000.00")

    # Create supplier
    sup = Supplier(
        business_id=biz.id,
        name="National Mills Ltd",
        standard_lead_time_days=10
    )
    db_session.add(sup)
    db_session.flush()

    assert sup.id is not None
    assert sup.name == "National Mills Ltd"

    # Create bank account
    bank = BankAccount(
        business_id=biz.id,
        account_name="HDFC Current Account",
        account_type="BANK",
        current_balance=Decimal("250000.00")
    )
    db_session.add(bank)
    db_session.commit()

    assert bank.id is not None
    assert bank.current_balance == Decimal("250000.00")


def test_invoice_and_allocation_lifecycle(db_session: Session):
    biz = Business(name="Apex Wholesale")
    db_session.add(biz)
    db_session.flush()

    cust = Customer(business_id=biz.id, name="City Grocers")
    bank = BankAccount(business_id=biz.id, account_name="Main Cash Till", account_type="CASH", current_balance=Decimal("50000.00"))
    db_session.add_all([cust, bank])
    db_session.flush()

    # Create invoice
    inv = SalesInvoice(
        business_id=biz.id,
        customer_id=cust.id,
        invoice_number="INV-2026-001",
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        total_amount=Decimal("100000.00"),
        paid_amount=Decimal("0.00"),
        status="ISSUED"
    )
    db_session.add(inv)
    db_session.flush()

    assert inv.unpaid_balance == Decimal("100000.00")

    # Create payment
    pmt = Payment(
        business_id=biz.id,
        customer_id=cust.id,
        bank_account_id=bank.id,
        payment_reference="PAY-1001",
        payment_date=date(2026, 10, 10),
        amount=Decimal("40000.00"),
        payment_method="NEFT",
        status="CLEARED",
        cleared_date=date(2026, 10, 10)
    )
    db_session.add(pmt)
    db_session.flush()

    # Allocate payment
    alloc = PaymentAllocation(
        payment_id=pmt.id,
        invoice_id=inv.id,
        allocated_amount=Decimal("40000.00")
    )
    inv.paid_amount += alloc.allocated_amount
    inv.status = "PARTIAL"
    db_session.add(alloc)
    db_session.commit()

    assert inv.paid_amount == Decimal("40000.00")
    assert inv.unpaid_balance == Decimal("60000.00")
    assert inv.status == "PARTIAL"


def test_supplier_advance_and_delivery(db_session: Session):
    biz = Business(name="Apex Wholesale")
    db_session.add(biz)
    db_session.flush()

    sup = Supplier(business_id=biz.id, name="Sunrise Agro")
    bank = BankAccount(business_id=biz.id, account_name="SBI Current", current_balance=Decimal("100000.00"))
    db_session.add_all([sup, bank])
    db_session.flush()

    # Advance
    adv = SupplierAdvance(
        business_id=biz.id,
        supplier_id=sup.id,
        bank_account_id=bank.id,
        advance_reference="ADV-501",
        disbursement_date=date(2026, 10, 5),
        expected_delivery_date=date(2026, 10, 20),
        advance_amount=Decimal("75000.00"),
        fulfilled_amount=Decimal("0.00"),
        status="DISBURSED"
    )
    db_session.add(adv)
    db_session.flush()

    assert adv.unfulfilled_balance == Decimal("75000.00")

    # Delivery
    deliv = Delivery(
        business_id=biz.id,
        supplier_id=sup.id,
        advance_id=adv.id,
        delivery_reference="DC-901",
        delivery_date=date(2026, 10, 18),
        delivered_value=Decimal("50000.00")
    )
    adv.fulfilled_amount += deliv.delivered_value
    adv.status = "PARTIAL_DELIVERED"
    db_session.add(deliv)
    db_session.commit()

    assert adv.unfulfilled_balance == Decimal("25000.00")
    assert adv.status == "PARTIAL_DELIVERED"


def test_financial_obligation(db_session: Session):
    biz = Business(name="Apex Wholesale")
    db_session.add(biz)
    db_session.flush()

    ob = FinancialObligation(
        business_id=biz.id,
        obligation_name="Warehouse Term Loan EMI",
        category="LOAN_EMI",
        due_date=date(2026, 11, 5),
        amount=Decimal("85000.00"),
        recipient="Axis Bank",
        status="SCHEDULED"
    )
    db_session.add(ob)
    db_session.commit()

    assert ob.id is not None
    assert ob.category == "LOAN_EMI"
    assert ob.amount == Decimal("85000.00")
