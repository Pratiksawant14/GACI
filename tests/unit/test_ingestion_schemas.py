"""
Unit tests for Ingestion Row Schemas and Validation rules (TSK-10).
"""

from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.ingestion import (
    CustomerImportRow,
    SupplierImportRow,
    InvoiceImportRow,
    AdvanceImportRow,
    PaymentImportRow,
    ObligationImportRow
)


def test_valid_invoice_row():
    row = InvoiceImportRow(
        invoice_number="INV-2026-001",
        customer_name="Super Mart",
        issue_date=date(2026, 10, 1),
        due_date=date(2026, 10, 20),
        total_amount=Decimal("150000.00"),
        paid_amount=Decimal("50000.00"),
        status="PARTIAL"
    )
    assert row.invoice_number == "INV-2026-001"
    assert row.total_amount == Decimal("150000.00")


def test_invalid_invoice_chronology():
    # due_date earlier than issue_date must fail validation
    with pytest.raises(ValidationError) as exc:
        InvoiceImportRow(
            invoice_number="INV-2026-002",
            customer_name="Super Mart",
            issue_date=date(2026, 10, 25),
            due_date=date(2026, 10, 10),
            total_amount=Decimal("100000.00")
        )
    assert "due_date" in str(exc.value)


def test_invoice_paid_amount_exceeding_total():
    with pytest.raises(ValidationError) as exc:
        InvoiceImportRow(
            invoice_number="INV-2026-003",
            customer_name="Super Mart",
            issue_date=date(2026, 10, 1),
            due_date=date(2026, 10, 15),
            total_amount=Decimal("50000.00"),
            paid_amount=Decimal("60000.00")
        )
    assert "paid_amount" in str(exc.value)


def test_invalid_advance_chronology():
    with pytest.raises(ValidationError) as exc:
        AdvanceImportRow(
            advance_reference="ADV-001",
            supplier_name="Global Agro",
            bank_account_name="Main Bank",
            disbursement_date=date(2026, 10, 20),
            expected_delivery_date=date(2026, 10, 5),
            advance_amount=Decimal("25000.00")
        )
    assert "expected_delivery_date" in str(exc.value)


def test_negative_amounts():
    with pytest.raises(ValidationError):
        CustomerImportRow(
            name="Negative Credit Cust",
            credit_limit=Decimal("-1000.00")
        )

    with pytest.raises(ValidationError):
        ObligationImportRow(
            obligation_name="Loan",
            category="LOAN_EMI",
            due_date=date(2026, 11, 1),
            amount=Decimal("-500.00")
        )
