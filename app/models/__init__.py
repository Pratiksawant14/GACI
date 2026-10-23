"""
Models package initialization.
Exports all canonical database entities for SQLAlchemy and Alembic.
"""

from app.models.base import Base, UUIDModel, GUID
from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import (
    SalesInvoice,
    Payment,
    PaymentAllocation,
    SupplierAdvance,
    Delivery,
    FinancialObligation,
    IngestionLog
)

__all__ = [
    "Base",
    "UUIDModel",
    "GUID",
    "Business",
    "Customer",
    "Supplier",
    "BankAccount",
    "SalesInvoice",
    "Payment",
    "PaymentAllocation",
    "SupplierAdvance",
    "Delivery",
    "FinancialObligation",
    "IngestionLog",
]
