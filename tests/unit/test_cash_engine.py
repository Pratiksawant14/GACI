"""
Unit tests for deterministic Cash Analysis Engine (TSK-13).
"""

from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import SalesInvoice, Payment, SupplierAdvance, FinancialObligation
from app.analysis.cash_engine import CashEngine


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)


def test_liquid_cash_calculation(session: Session):
    biz = Business(name="Apex Wholesale")
    session.add(biz)
    session.flush()

    b1 = BankAccount(business_id=biz.id, account_name="Bank A", current_balance=Decimal("150000.00"))
    b2 = BankAccount(business_id=biz.id, account_name="Cash Till", account_type="CASH", current_balance=Decimal("25000.50"))
    session.add_all([b1, b2])
    session.commit()

    engine = CashEngine(session)
    liquid = engine.calculate_liquid_cash(biz.id)
    assert liquid == Decimal("175000.50")


def test_overdue_receivables_and_aging(session: Session):
    biz = Business(name="Apex Wholesale")
    session.add(biz)
    session.flush()

    cust = Customer(business_id=biz.id, name="Metro Mart")
    session.add(cust)
    session.flush()

    # Invoices with various overdue ages as of 2026-10-15
    # 1. 15 days overdue (Bucket: 1-30 days)
    inv1 = SalesInvoice(
        business_id=biz.id, customer_id=cust.id, invoice_number="INV-01",
        issue_date=date(2026, 9, 1), due_date=date(2026, 9, 30),
        total_amount=Decimal("50000.00"), paid_amount=Decimal("0.00"), status="OVERDUE"
    )
    # 2. 45 days overdue (Bucket: 31-60 days)
    inv2 = SalesInvoice(
        business_id=biz.id, customer_id=cust.id, invoice_number="INV-02",
        issue_date=date(2026, 8, 1), due_date=date(2026, 8, 31),
        total_amount=Decimal("100000.00"), paid_amount=Decimal("20000.00"), status="OVERDUE"
    )
    # 3. Current (Not overdue)
    inv3 = SalesInvoice(
        business_id=biz.id, customer_id=cust.id, invoice_number="INV-03",
        issue_date=date(2026, 10, 1), due_date=date(2026, 10, 31),
        total_amount=Decimal("75000.00"), paid_amount=Decimal("0.00"), status="ISSUED"
    )
    session.add_all([inv1, inv2, inv3])
    session.commit()

    engine = CashEngine(session)
    blockages = engine.calculate_overdue_receivables(biz.id, as_of=date(2026, 10, 15))
    assert len(blockages) == 2

    buckets = engine.get_aging_buckets(blockages)
    b_1_30 = next(b for b in buckets if b.bucket == "1-30 days")
    b_31_60 = next(b for b in buckets if b.bucket == "31-60 days")

    assert b_1_30.count == 1
    assert b_1_30.total_amount == Decimal("50000.00")

    assert b_31_60.count == 1
    assert b_31_60.total_amount == Decimal("80000.00")  # 100k - 20k paid


def test_stranded_advances_and_bounced_cheque(session: Session):
    biz = Business(name="Apex Wholesale")
    session.add(biz)
    session.flush()

    sup = Supplier(business_id=biz.id, name="Agro Supplier")
    cust = Customer(business_id=biz.id, name="Retail Store")
    bank = BankAccount(business_id=biz.id, account_name="Main Bank", current_balance=Decimal("100000.00"))
    session.add_all([sup, cust, bank])
    session.flush()

    # Stranded advance (expected 2026-10-01, as_of 2026-10-15 = 14 days overdue)
    adv = SupplierAdvance(
        business_id=biz.id, supplier_id=sup.id, bank_account_id=bank.id,
        advance_reference="ADV-99", disbursement_date=date(2026, 9, 15),
        expected_delivery_date=date(2026, 10, 1),
        advance_amount=Decimal("120000.00"), fulfilled_amount=Decimal("20000.00"),
        status="DISBURSED"
    )
    # Bounced cheque
    pmt = Payment(
        business_id=biz.id, customer_id=cust.id, bank_account_id=bank.id,
        payment_reference="CHQ-77", payment_date=date(2026, 10, 10),
        amount=Decimal("45000.00"), payment_method="CHEQUE", status="BOUNCED"
    )
    session.add_all([adv, pmt])
    session.commit()

    engine = CashEngine(session)
    stranded = engine.calculate_stranded_advances(biz.id, as_of=date(2026, 10, 15))
    assert len(stranded) == 1
    assert stranded[0].amount == Decimal("100000.00")
    assert stranded[0].days_overdue == 14

    bounced = engine.calculate_bounced_cheque_exposure(biz.id, as_of=date(2026, 10, 15))
    assert len(bounced) == 1
    assert bounced[0].amount == Decimal("45000.00")


def test_cash_flow_projection_and_deficit_detection(session: Session):
    biz = Business(name="Apex Wholesale")
    session.add(biz)
    session.flush()

    # Liquid starting cash: 50,000
    bank = BankAccount(business_id=biz.id, account_name="Main Bank", current_balance=Decimal("50000.00"))
    cust = Customer(business_id=biz.id, name="Retail Store")
    session.add_all([bank, cust])
    session.flush()

    # Future receivable: 40,000 due on day 5 (2026-10-20)
    inv = SalesInvoice(
        business_id=biz.id, customer_id=cust.id, invoice_number="INV-FUT",
        issue_date=date(2026, 10, 1), due_date=date(2026, 10, 20),
        total_amount=Decimal("40000.00"), paid_amount=Decimal("0.00"), status="ISSUED"
    )

    # Future obligation: 120,000 loan due on day 10 (2026-10-25)
    # Total available before day 10: 50k + 40k = 90k.
    # On day 10: 90k - 120k = -30k deficit!
    ob = FinancialObligation(
        business_id=biz.id, bank_account_id=bank.id,
        obligation_name="Bank Loan EMI", category="LOAN_EMI",
        due_date=date(2026, 10, 25), amount=Decimal("120000.00"), status="SCHEDULED"
    )
    session.add_all([inv, ob])
    session.commit()

    engine = CashEngine(session)
    proj = engine.project_cash_flow(biz.id, as_of=date(2026, 10, 15), window_days=15)

    assert proj.starting_liquid_cash == Decimal("50000.00")
    assert proj.first_deficit_date == date(2026, 10, 25)
    assert proj.max_deficit_amount == Decimal("30000.00")
    assert proj.total_expected_inflows == Decimal("40000.00")
    assert proj.total_committed_outflows == Decimal("120000.00")
