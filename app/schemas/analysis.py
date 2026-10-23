"""
Pydantic Schemas for Deterministic Financial Analysis and Blockage Diagnostics.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field


class AgingBucketSummary(BaseModel):
    bucket: str  # "1-30 days", "31-60 days", "61-90 days", "90+ days"
    count: int = 0
    total_amount: Decimal = Decimal("0.00")


class CashSummary(BaseModel):
    as_of_date: date
    liquid_cash: Decimal = Decimal("0.00")
    total_overdue_receivables: Decimal = Decimal("0.00")
    total_stranded_advances: Decimal = Decimal("0.00")
    bounced_cheque_exposure: Decimal = Decimal("0.00")
    upcoming_obligations_15d: Decimal = Decimal("0.00")
    upcoming_obligations_30d: Decimal = Decimal("0.00")
    projected_net_position_15d: Decimal = Decimal("0.00")
    projected_net_position_30d: Decimal = Decimal("0.00")


class BlockageItem(BaseModel):
    blockage_id: str
    category: Literal["OVERDUE_RECEIVABLE", "STRANDED_ADVANCE", "BOUNCED_CHEQUE", "CASH_PRESSURE_DEFICIT"]
    entity_name: str
    entity_type: Literal["Customer", "Supplier", "BankAccount", "Obligation"]
    source_record_id: str
    amount: Decimal
    currency: str = "INR"
    due_or_disbursed_date: date
    days_overdue: int
    status: str
    severity_score: Decimal
    evidence_summary: str
    suggested_action: str


class DailyCashForecast(BaseModel):
    forecast_date: date
    day_offset: int
    opening_balance: Decimal
    expected_inflows: Decimal
    committed_outflows: Decimal
    closing_balance: Decimal
    has_deficit: bool


class CashProjectionReport(BaseModel):
    as_of_date: date
    starting_liquid_cash: Decimal
    forecast_horizon_days: int
    daily_forecasts: List[DailyCashForecast]
    first_deficit_date: Optional[date] = None
    max_deficit_amount: Decimal = Decimal("0.00")
    total_expected_inflows: Decimal = Decimal("0.00")
    total_committed_outflows: Decimal = Decimal("0.00")
