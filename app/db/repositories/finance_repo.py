"""
Financial Record Repositories.
Implements data access for SalesInvoice, Payment, SupplierAdvance, Delivery, and FinancialObligation.
"""

import uuid
from datetime import date
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from app.db.repositories.base_repo import BaseRepository
from app.models.finance import (
    SalesInvoice,
    Payment,
    PaymentAllocation,
    SupplierAdvance,
    Delivery,
    FinancialObligation,
    IngestionLog
)


class InvoiceRepository(BaseRepository[SalesInvoice]):
    def __init__(self, session: Session):
        super().__init__(SalesInvoice, session)

    def get_by_number(self, business_id: uuid.UUID, invoice_number: str) -> Optional[SalesInvoice]:
        stmt = select(SalesInvoice).where(
            SalesInvoice.business_id == business_id,
            SalesInvoice.invoice_number == invoice_number
        )
        return self.session.scalars(stmt).first()

    def get_overdue_invoices(self, business_id: uuid.UUID, as_of: date) -> List[SalesInvoice]:
        """Returns unpaid invoices where due_date < as_of and paid_amount < total_amount."""
        stmt = select(SalesInvoice).where(
            SalesInvoice.business_id == business_id,
            SalesInvoice.due_date < as_of,
            SalesInvoice.paid_amount < SalesInvoice.total_amount,
            SalesInvoice.status.notin_(["CANCELLED", "PAID"])
        ).order_by(SalesInvoice.due_date.asc())
        return list(self.session.scalars(stmt).all())

    def get_by_customer(self, customer_id: uuid.UUID) -> List[SalesInvoice]:
        stmt = select(SalesInvoice).where(SalesInvoice.customer_id == customer_id)
        return list(self.session.scalars(stmt).all())


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, session: Session):
        super().__init__(Payment, session)

    def get_by_reference(self, business_id: uuid.UUID, payment_reference: str) -> Optional[Payment]:
        stmt = select(Payment).where(
            Payment.business_id == business_id,
            Payment.payment_reference == payment_reference
        )
        return self.session.scalars(stmt).first()

    def get_bounced_payments(self, business_id: uuid.UUID) -> List[Payment]:
        stmt = select(Payment).where(
            Payment.business_id == business_id,
            Payment.status == "BOUNCED"
        )
        return list(self.session.scalars(stmt).all())


class AdvanceRepository(BaseRepository[SupplierAdvance]):
    def __init__(self, session: Session):
        super().__init__(SupplierAdvance, session)

    def get_by_reference(self, business_id: uuid.UUID, advance_reference: str) -> Optional[SupplierAdvance]:
        stmt = select(SupplierAdvance).where(
            SupplierAdvance.business_id == business_id,
            SupplierAdvance.advance_reference == advance_reference
        )
        return self.session.scalars(stmt).first()

    def get_stranded_advances(self, business_id: uuid.UUID, as_of: date) -> List[SupplierAdvance]:
        """Returns advances where expected_delivery_date < as_of and fulfilled_amount < advance_amount."""
        stmt = select(SupplierAdvance).where(
            SupplierAdvance.business_id == business_id,
            SupplierAdvance.expected_delivery_date < as_of,
            SupplierAdvance.fulfilled_amount < SupplierAdvance.advance_amount,
            SupplierAdvance.status.notin_(["FULFILLED", "REFUNDED"])
        ).order_by(SupplierAdvance.expected_delivery_date.asc())
        return list(self.session.scalars(stmt).all())


class ObligationRepository(BaseRepository[FinancialObligation]):
    def __init__(self, session: Session):
        super().__init__(FinancialObligation, session)

    def get_upcoming_obligations(self, business_id: uuid.UUID, start_date: date, end_date: date) -> List[FinancialObligation]:
        stmt = select(FinancialObligation).where(
            FinancialObligation.business_id == business_id,
            FinancialObligation.due_date >= start_date,
            FinancialObligation.due_date <= end_date,
            FinancialObligation.status == "SCHEDULED"
        ).order_by(FinancialObligation.due_date.asc())
        return list(self.session.scalars(stmt).all())


class IngestionLogRepository(BaseRepository[IngestionLog]):
    def __init__(self, session: Session):
        super().__init__(IngestionLog, session)

    def get_by_file_hash(self, file_hash: str) -> Optional[IngestionLog]:
        stmt = select(IngestionLog).where(IngestionLog.file_hash == file_hash)
        return self.session.scalars(stmt).first()
