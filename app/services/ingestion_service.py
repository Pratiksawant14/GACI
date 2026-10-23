"""
Business Data Ingestion Service.
Handles CSV/Excel parsing, row schema validation, duplicate deduplication,
transactional persistence to PostgreSQL, and post-commit graph projection.
"""

import hashlib
import io
import uuid
from datetime import date
from decimal import Decimal
from typing import Union, BinaryIO, Dict, Any, List
import pandas as pd
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.logging import logger
from app.graph.client import Neo4jClient, neo4j_client
from app.services.projection_service import ProjectionService
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
from app.schemas.ingestion import (
    CustomerImportRow,
    SupplierImportRow,
    BankAccountImportRow,
    InvoiceImportRow,
    PaymentImportRow,
    AdvanceImportRow,
    DeliveryImportRow,
    ObligationImportRow,
    IngestionReport,
    RowValidationError
)


class IngestionService:
    """Manages file ingestion, validation, persistence, and graph projection."""

    def __init__(self, session: Session, graph_client: Neo4jClient = neo4j_client):
        self.session = session
        self.projection_service = ProjectionService(session, graph_client)

    def parse_tabular_data(self, file_content: Union[str, bytes, BinaryIO], filename: str) -> List[Dict[str, Any]]:
        """Parses CSV or Excel into a list of row dictionaries."""
        if filename.endswith(".csv"):
            if isinstance(file_content, bytes):
                df = pd.read_csv(io.BytesIO(file_content))
            elif isinstance(file_content, str):
                df = pd.read_csv(file_content)
            else:
                df = pd.read_csv(file_content)
        elif filename.endswith((".xlsx", ".xls")):
            if isinstance(file_content, (bytes, io.BytesIO)):
                df = pd.read_excel(file_content)
            elif isinstance(file_content, str):
                df = pd.read_excel(file_content)
            else:
                df = pd.read_excel(file_content)
        else:
            raise ValueError(f"Unsupported file format: {filename}. Supported: .csv, .xlsx, .xls")

        # Replace NaN with None
        df = df.where(pd.notnull(df), None)
        return df.to_dict(orient="records")

    def ingest_table(
        self,
        business_id: uuid.UUID,
        file_content: Union[str, bytes, BinaryIO],
        table_type: str,
        filename: str = "uploaded_file.csv"
    ) -> IngestionReport:
        """Parses, validates, persists tabular data, and triggers graph sync."""
        records = self.parse_tabular_data(file_content, filename)
        report = IngestionReport(table_name=table_type, total_rows=len(records))

        # Calculate file hash for audit
        file_bytes = file_content if isinstance(file_content, bytes) else str(records).encode("utf-8")
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        valid_models = []

        for idx, row in enumerate(records, start=1):
            try:
                model = self._validate_and_build_model(business_id, table_type, row)
                if model:
                    valid_models.append(model)
                    report.valid_rows += 1
            except ValidationError as ve:
                err_msgs = [f"{err['loc'][0] if err['loc'] else 'row'}: {err['msg']}" for err in ve.errors()]
                report.errors.append(RowValidationError(row_number=idx, data=row, errors=err_msgs))
                report.error_rows += 1
            except Exception as exc:
                report.errors.append(RowValidationError(row_number=idx, data=row, errors=[str(exc)]))
                report.error_rows += 1

        # Transactional commit to PostgreSQL
        if valid_models:
            for item in valid_models:
                self.session.add(item)
            self.session.commit()

            # Post-commit Graph Projection
            try:
                self.projection_service.sync_all(business_id=business_id)
            except Exception as exc:
                logger.warning(f"Graph projection after ingestion encountered warning: {exc}")

        # Audit log entry
        report.status = "SUCCESS" if report.error_rows == 0 else ("PARTIAL" if report.valid_rows > 0 else "FAILED")
        log_entry = IngestionLog(
            business_id=business_id,
            file_name=filename,
            file_hash=file_hash,
            table_name=table_type,
            total_rows=report.total_rows,
            valid_rows=report.valid_rows,
            error_rows=report.error_rows,
            status=report.status,
            error_details=str([e.model_dump() for e in report.errors]) if report.errors else None
        )
        self.session.add(log_entry)
        self.session.commit()

        return report

    def _validate_and_build_model(self, business_id: uuid.UUID, table_type: str, row: Dict[str, Any]):
        """Validates row via Pydantic and returns SQLAlchemy entity or handles duplicates."""
        if table_type == "customers":
            parsed = CustomerImportRow(**row)
            # Deduplication: check existing customer
            existing = self.session.scalars(
                select(Customer).where(Customer.business_id == business_id, Customer.name == parsed.name)
            ).first()
            if existing:
                existing.credit_limit = parsed.credit_limit
                existing.standard_payment_terms_days = parsed.standard_payment_terms_days
                return existing
            return Customer(
                business_id=business_id,
                name=parsed.name,
                credit_limit=parsed.credit_limit,
                standard_payment_terms_days=parsed.standard_payment_terms_days,
                customer_code=parsed.customer_code,
                contact_email=parsed.contact_email,
                contact_phone=parsed.contact_phone
            )

        elif table_type == "suppliers":
            parsed = SupplierImportRow(**row)
            existing = self.session.scalars(
                select(Supplier).where(Supplier.business_id == business_id, Supplier.name == parsed.name)
            ).first()
            if existing:
                existing.standard_lead_time_days = parsed.standard_lead_time_days
                return existing
            return Supplier(
                business_id=business_id,
                name=parsed.name,
                standard_lead_time_days=parsed.standard_lead_time_days,
                supplier_code=parsed.supplier_code,
                contact_email=parsed.contact_email,
                contact_phone=parsed.contact_phone
            )

        elif table_type == "bank_accounts":
            parsed = BankAccountImportRow(**row)
            existing = self.session.scalars(
                select(BankAccount).where(BankAccount.business_id == business_id, BankAccount.account_name == parsed.account_name)
            ).first()
            if existing:
                existing.current_balance = parsed.current_balance
                return existing
            return BankAccount(
                business_id=business_id,
                account_name=parsed.account_name,
                account_type=parsed.account_type,
                current_balance=parsed.current_balance,
                account_number=parsed.account_number,
                bank_name=parsed.bank_name
            )

        elif table_type == "invoices":
            parsed = InvoiceImportRow(**row)
            # Find customer by name or customer_code
            cust = self.session.scalars(
                select(Customer).where(
                    Customer.business_id == business_id,
                    (Customer.name == parsed.customer_name) | (Customer.customer_code == parsed.customer_name)
                )
            ).first()
            if not cust:
                cust = Customer(business_id=business_id, name=parsed.customer_name)
                self.session.add(cust)
                self.session.flush()

            # Deduplication: check existing invoice
            existing_inv = self.session.scalars(
                select(SalesInvoice).where(SalesInvoice.business_id == business_id, SalesInvoice.invoice_number == parsed.invoice_number)
            ).first()
            if existing_inv:
                existing_inv.total_amount = parsed.total_amount
                existing_inv.paid_amount = parsed.paid_amount
                existing_inv.status = parsed.status
                return existing_inv

            return SalesInvoice(
                business_id=business_id,
                customer_id=cust.id,
                invoice_number=parsed.invoice_number,
                issue_date=parsed.issue_date,
                due_date=parsed.due_date,
                total_amount=parsed.total_amount,
                paid_amount=parsed.paid_amount,
                status=parsed.status
            )

        elif table_type == "payments":
            parsed = PaymentImportRow(**row)
            # Find bank account
            bank = self.session.scalars(
                select(BankAccount).where(BankAccount.business_id == business_id, BankAccount.account_name == parsed.bank_account_name)
            ).first()
            if not bank:
                bank = BankAccount(business_id=business_id, account_name=parsed.bank_account_name, account_type="BANK")
                self.session.add(bank)
                self.session.flush()

            # Find customer if provided
            cust_id = None
            if parsed.customer_name:
                cust = self.session.scalars(
                    select(Customer).where(Customer.business_id == business_id, Customer.name == parsed.customer_name)
                ).first()
                if cust:
                    cust_id = cust.id

            existing_pmt = self.session.scalars(
                select(Payment).where(Payment.business_id == business_id, Payment.payment_reference == parsed.payment_reference)
            ).first()
            if existing_pmt:
                existing_pmt.status = parsed.status
                existing_pmt.amount = parsed.amount
                return existing_pmt

            pmt = Payment(
                business_id=business_id,
                customer_id=cust_id,
                bank_account_id=bank.id,
                payment_reference=parsed.payment_reference,
                payment_date=parsed.payment_date,
                amount=parsed.amount,
                payment_method=parsed.payment_method,
                status=parsed.status,
                cleared_date=parsed.payment_date if parsed.status == "CLEARED" else None
            )

            # Auto-allocate to invoice if specified
            if parsed.invoice_number:
                inv = self.session.scalars(
                    select(SalesInvoice).where(SalesInvoice.business_id == business_id, SalesInvoice.invoice_number == parsed.invoice_number)
                ).first()
                if inv:
                    alloc_amt = parsed.allocated_amount or parsed.amount
                    alloc = PaymentAllocation(payment_id=pmt.id, invoice_id=inv.id, allocated_amount=alloc_amt)
                    pmt.allocations.append(alloc)
                    inv.paid_amount += alloc_amt
                    if inv.paid_amount >= inv.total_amount:
                        inv.status = "PAID"
                    else:
                        inv.status = "PARTIAL"

            return pmt

        elif table_type == "advances":
            parsed = AdvanceImportRow(**row)
            sup = self.session.scalars(
                select(Supplier).where(Supplier.business_id == business_id, Supplier.name == parsed.supplier_name)
            ).first()
            if not sup:
                sup = Supplier(business_id=business_id, name=parsed.supplier_name)
                self.session.add(sup)
                self.session.flush()

            bank = self.session.scalars(
                select(BankAccount).where(BankAccount.business_id == business_id, BankAccount.account_name == parsed.bank_account_name)
            ).first()
            if not bank:
                bank = BankAccount(business_id=business_id, account_name=parsed.bank_account_name)
                self.session.add(bank)
                self.session.flush()

            existing_adv = self.session.scalars(
                select(SupplierAdvance).where(SupplierAdvance.business_id == business_id, SupplierAdvance.advance_reference == parsed.advance_reference)
            ).first()
            if existing_adv:
                existing_adv.fulfilled_amount = parsed.fulfilled_amount
                existing_adv.status = parsed.status
                return existing_adv

            return SupplierAdvance(
                business_id=business_id,
                supplier_id=sup.id,
                bank_account_id=bank.id,
                advance_reference=parsed.advance_reference,
                disbursement_date=parsed.disbursement_date,
                expected_delivery_date=parsed.expected_delivery_date,
                advance_amount=parsed.advance_amount,
                fulfilled_amount=parsed.fulfilled_amount,
                status=parsed.status
            )

        elif table_type == "deliveries":
            parsed = DeliveryImportRow(**row)
            sup = self.session.scalars(
                select(Supplier).where(Supplier.business_id == business_id, Supplier.name == parsed.supplier_name)
            ).first()
            if not sup:
                sup = Supplier(business_id=business_id, name=parsed.supplier_name)
                self.session.add(sup)
                self.session.flush()

            adv_id = None
            if parsed.advance_reference:
                adv = self.session.scalars(
                    select(SupplierAdvance).where(SupplierAdvance.business_id == business_id, SupplierAdvance.advance_reference == parsed.advance_reference)
                ).first()
                if adv:
                    adv_id = adv.id
                    adv.fulfilled_amount += parsed.delivered_value
                    if adv.fulfilled_amount >= adv.advance_amount:
                        adv.status = "FULFILLED"
                    else:
                        adv.status = "PARTIAL_DELIVERED"

            existing_deliv = self.session.scalars(
                select(Delivery).where(Delivery.business_id == business_id, Delivery.delivery_reference == parsed.delivery_reference)
            ).first()
            if existing_deliv:
                return existing_deliv

            return Delivery(
                business_id=business_id,
                supplier_id=sup.id,
                advance_id=adv_id,
                delivery_reference=parsed.delivery_reference,
                delivery_date=parsed.delivery_date,
                delivered_value=parsed.delivered_value
            )

        elif table_type == "obligations":
            parsed = ObligationImportRow(**row)
            bank_id = None
            if parsed.bank_account_name:
                bank = self.session.scalars(
                    select(BankAccount).where(BankAccount.business_id == business_id, BankAccount.account_name == parsed.bank_account_name)
                ).first()
                if bank:
                    bank_id = bank.id

            existing_ob = self.session.scalars(
                select(FinancialObligation).where(
                    FinancialObligation.business_id == business_id,
                    FinancialObligation.obligation_name == parsed.obligation_name,
                    FinancialObligation.due_date == parsed.due_date
                )
            ).first()
            if existing_ob:
                existing_ob.status = parsed.status
                existing_ob.amount = parsed.amount
                return existing_ob

            return FinancialObligation(
                business_id=business_id,
                bank_account_id=bank_id,
                obligation_name=parsed.obligation_name,
                category=parsed.category,
                due_date=parsed.due_date,
                amount=parsed.amount,
                recipient=parsed.recipient,
                status=parsed.status
            )

        else:
            raise ValueError(f"Unknown table type: {table_type}")
