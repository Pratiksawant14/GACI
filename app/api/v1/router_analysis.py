"""
Deterministic Cash-Flow Analysis Endpoints.
Exposes real-time liquid balance, blockage severity rankings,
accounts receivable aging brackets, and forward-looking cash deficit projections.
"""

from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_active_business
from app.models.entities import Business
from app.analysis.cash_engine import CashEngine
from app.schemas.analysis import (
    CashSummary,
    BlockageItem,
    AgingBucketSummary,
    CashProjectionReport
)

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("/cash-summary", response_model=CashSummary, summary="Get Real-Time Cash Summary")
def get_cash_summary(
    as_of: Optional[date] = Query(None, description="Analysis reference date (defaults to today)"),
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
) -> CashSummary:
    """Returns verified liquid balances, outstanding A/R, stranded advances, and scheduled obligations."""
    calc_date = as_of or date.today()
    engine = CashEngine(db)
    return engine.get_cash_summary(business_id=business.id, as_of=calc_date)


@router.get("/blockages", response_model=List[BlockageItem], summary="Get Prioritized Cash Blockages")
def get_cash_blockages(
    as_of: Optional[date] = Query(None, description="Analysis reference date (defaults to today)"),
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
) -> List[BlockageItem]:
    """Returns all overdue receivables, stranded advances, and bounced cheques ranked by severity score."""
    calc_date = as_of or date.today()
    engine = CashEngine(db)
    return engine.get_all_blockages(business_id=business.id, as_of=calc_date)


@router.get("/cash-projection", response_model=CashProjectionReport, summary="Get Forward Cash-Flow Projection")
def get_cash_projection(
    as_of: Optional[date] = Query(None, description="Projection starting date (defaults to today)"),
    horizon_days: int = Query(30, ge=1, le=90, description="Forecast horizon in days (e.g. 7, 15, 30)"),
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
) -> CashProjectionReport:
    """Projects daily closing balances and detects impending liquidity deficit dates."""
    calc_date = as_of or date.today()
    engine = CashEngine(db)
    return engine.project_cash_flow(business_id=business.id, as_of=calc_date, window_days=horizon_days)


@router.get("/aging-buckets", response_model=List[AgingBucketSummary], summary="Get Accounts Receivable Aging Buckets")
def get_aging_buckets(
    as_of: Optional[date] = Query(None, description="Aging reference date (defaults to today)"),
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
) -> List[AgingBucketSummary]:
    """Returns total accounts receivable categorized into standard 1-30, 31-60, 61-90, and 90+ day aging buckets."""
    calc_date = as_of or date.today()
    engine = CashEngine(db)
    overdue_blockages = engine.calculate_overdue_receivables(business_id=business.id, as_of=calc_date)
    return engine.get_aging_buckets(blockages=overdue_blockages)
