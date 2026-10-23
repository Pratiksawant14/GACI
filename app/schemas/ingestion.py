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


def _clean_str(v: Any) -> Optional[str]:
    """Helper to cleanly coerce int/float/string to trimmed string or None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(int(v)) if isinstance(v, (int, float)) and not pd.isna(v) and float(v).is_integer() else str(v).strip()
    return None if s == "" or s.lower() == "nan" else s


class CustomerImportRow(BaseModel):
    name: str = Field(..., min_length=1, description="Customer commercial name")
    credit_limit: Decimal = Field(default=Decimal("0.00"), ge=0, description="Authorized credit limit")
    standard_payment_terms_days: int = Field(default=30, ge=0, description="Credit payment term in days")
    customer_code: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Column aliases
            if "customer_id" in data and "customer_code" not in data:
                data["customer_code"] = data["customer_id"]
            if "payment_terms_days" in data and "standard_payment_terms_days" not in data:
                data["standard_payment_terms_days"] = data["payment_terms_days"]
            elif "payment_terms" in data and "standard_payment_terms_days" not in data:
                data["standard_payment_terms_days"] = data["payment_terms"]
            if "phone" in data and "contact_phone" not in data:
                data["contact_phone"] = data["phone"]
            if "email" in data and "contact_email" not in data:
                data["contact_email"] = data["email"]
        return data

    @field_validator("contact_phone", "customer_code", mode="before")
    @classmethod
    def clean_strings(cls, v):
        return _clean_str(v)


class SupplierImportRow(BaseModel):
    name: str = Field(..., min_length=1, description="Supplier commercial name")
    standard_lead_time_days: int = Field(default=14, ge=0, description="Lead time in days")
    supplier_code: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "supplier_id" in data and "supplier_code" not in data:
                data["supplier_code"] = data["supplier_id"]
            if "lead_time_days" in data and "standard_lead_time_days" not in data:
                data["standard_lead_time_days"] = data["lead_time_days"]
            elif "lead_time" in data and "standard_lead_time_days" not in data:
                data["standard_lead_time_days"] = data["lead_time"]
            if "phone" in data and "contact_phone" not in data:
                data["contact_phone"] = data["phone"]
            if "email" in data and "contact_email" not in data:
                data["contact_email"] = data["email"]
        return data

    @field_validator("contact_phone", "supplier_code", mode="before")
    @classmethod
    def clean_strings(cls, v):
        return _clean_str(v)


class BankAccountImportRow(BaseModel):
    account_name: str = Field(..., min_length=1)
    account_type: Literal["BANK", "CASH"] = "BANK"
    current_balance: Decimal = Field(default=Decimal("0.00"))
    account_number: Optional[str] = None
    bank_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "account_id" in data and "account_number" not in data:
                data["account_number"] = data["account_id"]
            if "balance" in data and "current_balance" not in data:
                data["current_balance"] = data["balance"]
            # Normalize common account types
            t = str(data.get("account_type", "")).upper().strip()
            if t in ["CURRENT", "SAVINGS", "OVERDRAFT", "CHECKING", "BANK"]:
                data["account_type"] = "BANK"
            elif t in ["CASH_TILL", "PETTY_CASH", "CASH"]:
                data["account_type"] = "CASH"
        return data

    @field_validator("account_number", mode="before")
    @classmethod
    def clean_account_number(cls, v):
        return _clean_str(v)


class InvoiceImportRow(BaseModel):
    invoice_number: str = Field(..., min_length=1)
    customer_name: str = Field(..., min_length=1)
    issue_date: date
    due_date: date
    total_amount: Decimal = Field(..., gt=0)
    paid_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    status: Literal["ISSUED", "PARTIAL", "PAID", "OVERDUE", "CANCELLED"] = "ISSUED"

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "invoice_id" in data and "invoice_number" not in data:
                data["invoice_number"] = data["invoice_id"]
            if "customer_id" in data and "customer_name" not in data:
                data["customer_name"] = data["customer_id"]
            # Normalize invoice status flexibly
            st = str(data.get("status", "")).upper().strip()
            if "PARTIAL" in st:
                data["status"] = "PARTIAL"
            elif st in ["PAID", "CLEARED", "SETTLED"]:
                data["status"] = "PAID"
            elif st in ["OVERDUE", "LATE"]:
                data["status"] = "OVERDUE"
            elif st in ["CANCELLED", "VOID"]:
                data["status"] = "CANCELLED"
            elif st in ["ISSUED", "OPEN", "UNPAID", "PENDING"]:
                data["status"] = "ISSUED"
        return data

    @field_validator("invoice_number", "customer_name", mode="before")
    @classmethod
    def clean_strings(cls, v):
        return _clean_str(v)

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

    @field_validator("payment_reference", mode="before")
    @classmethod
    def clean_ref(cls, v):
        return _clean_str(v)


class AdvanceImportRow(BaseModel):
    advance_reference: str = Field(..., min_length=1)
    supplier_name: str = Field(..., min_length=1)
    bank_account_name: str = Field(..., min_length=1)
    disbursement_date: date
    expected_delivery_date: date
    advance_amount: Decimal = Field(..., gt=0)
    fulfilled_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    status: Literal["DISBURSED", "PARTIAL_DELIVERED", "FULFILLED", "REFUNDED"] = "DISBURSED"

    @field_validator("advance_reference", mode="before")
    @classmethod
    def clean_ref(cls, v):
        return _clean_str(v)

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

    @field_validator("delivery_reference", "advance_reference", mode="before")
    @classmethod
    def clean_ref(cls, v):
        return _clean_str(v)


class ObligationImportRow(BaseModel):
    obligation_name: str = Field(..., min_length=1)
    category: Literal["LOAN_EMI", "RENT", "TAX", "PAYROLL", "SUPPLIER_PAYABLE"] = "LOAN_EMI"
    due_date: date
    amount: Decimal = Field(..., gt=0)
    bank_account_name: Optional[str] = None
    recipient: Optional[str] = None
    status: Literal["SCHEDULED", "PAID", "OVERDUE", "DEFAULTED"] = "SCHEDULED"

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "type" in data and "category" not in data:
                data["category"] = data["type"]
            # Normalize obligation status flexibly
            st = str(data.get("status", "")).upper().strip()
            if st in ["PENDING", "SCHEDULED", "UPCOMING", "ACTIVE", "DUE", "UNPAID"]:
                data["status"] = "SCHEDULED"
            elif st in ["PAID", "CLEARED", "COMPLETED", "SETTLED"]:
                data["status"] = "PAID"
            elif st in ["OVERDUE", "LATE"]:
                data["status"] = "OVERDUE"
            elif st in ["DEFAULTED", "BOUNCED", "FAILED"]:
                data["status"] = "DEFAULTED"
        return data


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
