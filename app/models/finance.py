"""
Financial and Operational Models.
Defines SalesInvoice, Payment, PaymentAllocation, SupplierAdvance, Delivery, FinancialObligation, and IngestionLog.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import String, Numeric, Integer, Date, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import UUIDModel, GUID


class SalesInvoice(UUIDModel):
    """Commercial sales invoice billed to a customer on credit terms."""
    __tablename__ = "sales_invoices"
    __table_args__ = (
        UniqueConstraint("business_id", "invoice_number", name="uq_business_invoice_number"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ISSUED", nullable=False, index=True)  # ISSUED, PARTIAL, PAID, OVERDUE, CANCELLED

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="invoices")
    allocations: Mapped[List["PaymentAllocation"]] = relationship("PaymentAllocation", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def unpaid_balance(self) -> Decimal:
        return max(Decimal("0.00"), self.total_amount - self.paid_amount)


class Payment(UUIDModel):
    """Financial transaction receipt or collection."""
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("business_id", "payment_reference", name="uq_business_payment_reference"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    payment_reference: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), default="BANK_TRANSFER", nullable=False)  # CASH, CHEQUE, NEFT, RTGS, UPI
    status: Mapped[str] = mapped_column(String(50), default="INITIATED", nullable=False, index=True)  # INITIATED, CLEARED, BOUNCED, REVERSED
    cleared_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Relationships
    customer: Mapped[Optional["Customer"]] = relationship("Customer", back_populates="payments")
    bank_account: Mapped["BankAccount"] = relationship("BankAccount")
    allocations: Mapped[List["PaymentAllocation"]] = relationship("PaymentAllocation", back_populates="payment", cascade="all, delete-orphan")


class PaymentAllocation(UUIDModel):
    """Double-entry linkage allocating confirmed cash receipt to an invoice."""
    __tablename__ = "payment_allocations"
    __table_args__ = (
        UniqueConstraint("payment_id", "invoice_id", name="uq_payment_invoice_allocation"),
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Relationships
    payment: Mapped["Payment"] = relationship("Payment", back_populates="allocations")
    invoice: Mapped["SalesInvoice"] = relationship("SalesInvoice", back_populates="allocations")


class SupplierAdvance(UUIDModel):
    """Working capital advance disbursed to supplier prior to delivery."""
    __tablename__ = "supplier_advances"
    __table_args__ = (
        UniqueConstraint("business_id", "advance_reference", name="uq_business_advance_reference"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_account_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bank_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    advance_reference: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    disbursement_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    expected_delivery_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    advance_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    fulfilled_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DISBURSED", nullable=False, index=True)  # DISBURSED, PARTIAL_DELIVERED, FULFILLED, REFUNDED

    # Relationships
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="advances")
    bank_account: Mapped["BankAccount"] = relationship("BankAccount")
    deliveries: Mapped[List["Delivery"]] = relationship("Delivery", back_populates="advance")

    @property
    def unfulfilled_balance(self) -> Decimal:
        return max(Decimal("0.00"), self.advance_amount - self.fulfilled_amount)


class Delivery(UUIDModel):
    """Physical delivery of merchandise fulfilling purchase orders or advances."""
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("business_id", "delivery_reference", name="uq_business_delivery_reference"),
    )

    business_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    advance_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("supplier_advances.id", ondelete="SET NULL"), nullable=True, index=True)
    delivery_reference: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    delivered_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    # Relationships
    supplier: Mapped["Supplier"] = relationship("Supplier", back_populates="deliveries")
    advance: Mapped[Optional["SupplierAdvance"]] = relationship("SupplierAdvance", back_populates="deliveries")


class FinancialObligation(UUIDModel):
    """Contractual future cash outflow with strict deadline (EMI, Rent, Tax, Payroll)."""
    __tablename__ = "financial_obligations"

    business_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    bank_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("bank_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    obligation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # LOAN_EMI, RENT, TAX, PAYROLL, SUPPLIER_PAYABLE
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    recipient: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="SCHEDULED", nullable=False, index=True)  # SCHEDULED, PAID, OVERDUE, DEFAULTED

    # Relationships
    bank_account: Mapped[Optional["BankAccount"]] = relationship("BankAccount")


class IngestionLog(UUIDModel):
    """Audit log tracking file uploads, validation results, and ingestion history."""
    __tablename__ = "ingestion_logs"

    business_id: Mapped[Optional[uuid.UUID]] = mapped_column(GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="SUCCESS", nullable=False)  # SUCCESS, PARTIAL, FAILED
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
