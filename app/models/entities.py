"""
Commercial Counterparty and Account Entities.
Defines Business, Customer, Supplier, and BankAccount models.
"""

import uuid
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import String, Numeric, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import UUIDModel, GUID


class Business(UUIDModel):
    """The central wholesale MSME company profile."""
    __tablename__ = "businesses"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    registration_number: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    fiscal_year_start_month: Mapped[int] = mapped_column(Integer, default=4, nullable=False)

    # Relationships
    customers: Mapped[List["Customer"]] = relationship("Customer", back_populates="business", cascade="all, delete-orphan")
    suppliers: Mapped[List["Supplier"]] = relationship("Supplier", back_populates="business", cascade="all, delete-orphan")
    bank_accounts: Mapped[List["BankAccount"]] = relationship("BankAccount", back_populates="business", cascade="all, delete-orphan")


class Customer(UUIDModel):
    """Wholesale commercial customer receiving trade credit."""
    __tablename__ = "customers"

    business_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    customer_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    standard_payment_terms_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="customers")
    invoices: Mapped[List["SalesInvoice"]] = relationship("SalesInvoice", back_populates="customer", cascade="all, delete-orphan")
    payments: Mapped[List["Payment"]] = relationship("Payment", back_populates="customer", cascade="all, delete-orphan")


class Supplier(UUIDModel):
    """Merchandise or raw material vendor."""
    __tablename__ = "suppliers"

    business_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    supplier_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    standard_lead_time_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="suppliers")
    advances: Mapped[List["SupplierAdvance"]] = relationship("SupplierAdvance", back_populates="supplier", cascade="all, delete-orphan")
    deliveries: Mapped[List["Delivery"]] = relationship("Delivery", back_populates="supplier", cascade="all, delete-orphan")


class BankAccount(UUIDModel):
    """Liquid commercial depository (Bank account or Physical Cash Till)."""
    __tablename__ = "bank_accounts"

    business_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    account_type: Mapped[str] = mapped_column(String(50), default="BANK", nullable=False)  # "BANK" or "CASH"
    current_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="bank_accounts")
