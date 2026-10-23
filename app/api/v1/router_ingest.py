"""
Data Ingestion REST Endpoints.
Handles single and multi-file uploads of wholesale financial ledgers,
runs schema validation, commits to PostgreSQL, and triggers graph projection.
"""

import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_active_business
from app.models.entities import Business
from app.services.ingestion_service import IngestionService
from app.schemas.api import IngestionSummaryResponse
from app.core.logging import logger

router = APIRouter(prefix="/ingest", tags=["Ingestion"])


def detect_table_type(filename: str, explicit_type: Optional[str] = None) -> str:
    """Infers canonical table type from explicit form parameter or filename."""
    if explicit_type and explicit_type.strip():
        clean_type = explicit_type.strip().lower()
        valid_types = {
            "customers", "suppliers", "bank_accounts", "invoices",
            "payments", "advances", "deliveries", "obligations"
        }
        if clean_type in valid_types:
            return clean_type

    lower_name = filename.lower()
    if "customer" in lower_name:
        return "customers"
    elif "supplier" in lower_name:
        return "suppliers"
    elif "bank" in lower_name or "account" in lower_name:
        return "bank_accounts"
    elif "invoice" in lower_name or "sales" in lower_name:
        return "invoices"
    elif "payment" in lower_name:
        return "payments"
    elif "advance" in lower_name:
        return "advances"
    elif "deliver" in lower_name:
        return "deliveries"
    elif "obligation" in lower_name or "loan" in lower_name:
        return "obligations"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unable to determine table type for file '{filename}'. Specify 'table_type' explicitly."
    )


@router.post("/upload", response_model=IngestionSummaryResponse, summary="Upload and Ingest Ledger Files")
async def upload_files(
    files: List[UploadFile] = File(...),
    table_type: Optional[str] = Form(None),
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
) -> IngestionSummaryResponse:
    """
    Accepts one or more CSV/Excel files, validates schema rules,
    persists valid records to PostgreSQL, and triggers graph synchronization.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided for upload."
        )

    service = IngestionService(db)
    reports = []

    for upload_file in files:
        target_type = detect_table_type(upload_file.filename, table_type if len(files) == 1 else None)
        content = await upload_file.read()

        logger.info(f"Processing upload for file: {upload_file.filename} as {target_type}")
        report = service.ingest_table(
            business_id=business.id,
            file_content=content,
            table_type=target_type,
            filename=upload_file.filename
        )
        reports.append(report.model_dump())

    return IngestionSummaryResponse(
        business_id=business.id,
        business_name=business.name,
        reports=reports,
        total_files_processed=len(files),
        graph_synced=True
    )


@router.post("/reset", summary="Reset and Wipe All Business Financial Data")
def reset_business_data(
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
):
    """
    Clears all financial transactions, ledgers, accounts, counterparties,
    and ingestion logs for the active business, returning it to a completely empty state.
    """
    from app.models.finance import (
        PaymentAllocation, Payment, Delivery,
        SupplierAdvance, SalesInvoice, FinancialObligation,
        IngestionLog
    )
    from app.models.entities import BankAccount, Customer, Supplier

    # Delete in child-to-parent order to respect foreign keys
    db.query(PaymentAllocation).filter(PaymentAllocation.payment_id.in_(
        db.query(Payment.id).filter(Payment.business_id == business.id)
    )).delete(synchronize_session=False)

    db.query(Payment).filter(Payment.business_id == business.id).delete(synchronize_session=False)
    db.query(Delivery).filter(Delivery.business_id == business.id).delete(synchronize_session=False)
    db.query(SupplierAdvance).filter(SupplierAdvance.business_id == business.id).delete(synchronize_session=False)
    db.query(SalesInvoice).filter(SalesInvoice.business_id == business.id).delete(synchronize_session=False)
    db.query(FinancialObligation).filter(FinancialObligation.business_id == business.id).delete(synchronize_session=False)
    db.query(BankAccount).filter(BankAccount.business_id == business.id).delete(synchronize_session=False)
    db.query(Customer).filter(Customer.business_id == business.id).delete(synchronize_session=False)
    db.query(Supplier).filter(Supplier.business_id == business.id).delete(synchronize_session=False)
    db.query(IngestionLog).filter(IngestionLog.business_id == business.id).delete(synchronize_session=False)

    db.commit()
    logger.info(f"Successfully purged all transactional records for business {business.id}")
    return {
        "status": "success",
        "message": f"All financial records for '{business.name}' have been wiped. Database is completely clean (0 records)."
    }
