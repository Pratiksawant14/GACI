"""
Pydantic v2 Ingestion Validation Schemas.
Enforces strict column validation, date chronological consistency, and non-negative amounts.
"""

from datetime import date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator, field_validator
import pandas as pd
import math


class CustomerImportRow(BaseModel):
    name: str = Field(..., min_length=1, description="Customer commercial name")
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0, description="Authorized credit limit")
    standard_payment_terms_days: int = Field(default=30, ge=0, description="Credit payment term in days")
    customer_code: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class SupplierImportRow(BaseModel):
    name: str = Field(..., min_length=1, description="Supplier commercial name")
    standard_lead_time_days: int = Field(default=14, ge=0, description="Lead time in days")
    supplier_code: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class BankAccountImportRow(BaseModel):
    account_name: str = Field(..., min_length=1)
    account_type: Literal["BANK", "CASH"] = "BANK"
    current_balance: Decimal = Field(default=Decimal("0.00"))
    account_number: Optional[str] = None
    bank_name: Optional[str] = None

    @field_validator("account_number", mode="before")
    @classmethod
    def clean_account_number(cls, v):
        if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "" or str(v).lower() == "nan":
            return None
        if isinstance(v, (int, float)):
            return str(int(v))
        return str(v).strip()


class InvoiceImportRow(BaseModel):
    invoice_number: str = Field(..., min_length=1)
    customer_name: str = Field(..., min_length=1)
    issue_date: date
    due_date: date
    total_amount: Decimal = Field(..., gt=0)
    paid_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    status: Literal["ISSUED", "PARTIAL", "PAID", "OVERDUE", "CANCELLED"] = "ISSUED"

    @model_validator(mode="after")
    def validate_dates_and_amounts(self) -> "InvoiceImportRow":
        if self.due_date < self.issue_date:
            raise ValueError(f"Invoice due_date ({self.due_date}) cannot be earlier than issue_date ({self.issue_date})")
        if self.paid_amount > self.total_amount:
            raise ValueError(f"paid_amount ({self.paid_amount}) cannot exceed total_amount ({self.total_amount})")
        return self


class PaymentImportRow(BaseModel):
    payment_reference: str = Field(..., min_length=1)
    bank_account_name: str = Field(..., min_length=1)
    customer_name: Optional[str] = None
    payment_date: date
    amount: Decimal = Field(..., gt=0)
    payment_method: Literal["CASH", "CHEQUE", "NEFT", "RTGS", "UPI", "BANK_TRANSFER"] = "BANK_TRANSFER"
    status: Literal["INITIATED", "CLEARED", "BOUNCED", "REVERSED"] = "CLEARED"
    invoice_number: Optional[str] = None  # If direct allocation is provided in file
    allocated_amount: Optional[Decimal] = None


class AdvanceImportRow(BaseModel):
    advance_reference: str = Field(..., min_length=1)
    supplier_name: str = Field(..., min_length=1)
    bank_account_name: str = Field(..., min_length=1)
    disbursement_date: date
    expected_delivery_date: date
    advance_amount: Decimal = Field(..., gt=0)
    fulfilled_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    status: Literal["DISBURSED", "PARTIAL_DELIVERED", "FULFILLED", "REFUNDED"] = "DISBURSED"

    @model_validator(mode="after")
    def validate_dates(self) -> "AdvanceImportRow":
        if self.expected_delivery_date < self.disbursement_date:
            raise ValueError(f"expected_delivery_date ({self.expected_delivery_date}) cannot precede disbursement_date ({self.disbursement_date})")
        return self


class DeliveryImportRow(BaseModel):
    delivery_reference: str = Field(..., min_length=1)
    supplier_name: str = Field(..., min_length=1)
    advance_reference: Optional[str] = None
    delivery_date: date
    delivered_value: Decimal = Field(..., gt=0)


class ObligationImportRow(BaseModel):
    obligation_name: str = Field(..., min_length=1)
    category: Literal["LOAN_EMI", "RENT", "TAX", "PAYROLL", "SUPPLIER_PAYABLE"] = "LOAN_EMI"
    due_date: date
    amount: Decimal = Field(..., gt=0)
    bank_account_name: Optional[str] = None
    recipient: Optional[str] = None
    status: Literal["SCHEDULED", "PAID", "OVERDUE", "DEFAULTED"] = "SCHEDULED"


class RowValidationError(BaseModel):
    row_number: int
    data: Dict[str, Any]
    errors: List[str]


class IngestionReport(BaseModel):
    table_name: str
    total_rows: int = 0
    valid_rows: int = 0
    error_rows: int = 0
    errors: List[RowValidationError] = []
    status: Literal["SUCCESS", "PARTIAL", "FAILED"] = "SUCCESS"
