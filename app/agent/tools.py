"""
Deterministic Analysis Tools for Agent Workflow.
Wraps core cash calculation and graph contagion engines into structured,
deterministic tool functions returning validated database evidence.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.analysis.cash_engine import CashEngine
from app.graph.contagion import GraphContagionEngine
from app.core.logging import logger


class AgentToolSuite:
    """Provides callable deterministic intelligence tools for the LangGraph state machine."""

    def __init__(self, db: Session):
        self.db = db
        self.cash_engine = CashEngine(db)
        self.contagion_engine = GraphContagionEngine(db)

    def get_cash_summary_tool(self, business_id: uuid.UUID, as_of: date) -> Dict[str, Any]:
        """Calculates verified liquid balances, overdue receivables, stranded advances, and obligations."""
        summary = self.cash_engine.get_cash_summary(business_id=business_id, as_of=as_of)
        return {
            "as_of_date": str(summary.as_of_date),
            "liquid_cash": float(summary.liquid_cash),
            "total_overdue_receivables": float(summary.total_overdue_receivables),
            "total_stranded_advances": float(summary.total_stranded_advances),
            "bounced_cheque_exposure": float(summary.bounced_cheque_exposure),
            "upcoming_obligations_15d": float(summary.upcoming_obligations_15d),
            "upcoming_obligations_30d": float(summary.upcoming_obligations_30d),
            "projected_net_position_15d": float(summary.projected_net_position_15d),
            "projected_net_position_30d": float(summary.projected_net_position_30d),
        }

    def get_overdue_receivables_tool(self, business_id: uuid.UUID, as_of: date) -> List[Dict[str, Any]]:
        """Identifies unpaid invoices past due date with aging and severity scores."""
        blockages = self.cash_engine.calculate_overdue_receivables(business_id=business_id, as_of=as_of)
        return [
            {
                "blockage_id": b.blockage_id,
                "customer_name": b.entity_name,
                "amount": float(b.amount),
                "due_date": str(b.due_or_disbursed_date),
                "days_overdue": b.days_overdue,
                "severity_score": float(b.severity_score),
                "evidence": b.evidence_summary,
                "suggested_action": b.suggested_action
            }
            for b in blockages
        ]

    def get_stranded_advances_tool(self, business_id: uuid.UUID, as_of: date) -> List[Dict[str, Any]]:
        """Identifies advances paid to suppliers where goods were not delivered on schedule."""
        advances = self.cash_engine.calculate_stranded_advances(business_id=business_id, as_of=as_of)
        return [
            {
                "blockage_id": a.blockage_id,
                "supplier_name": a.entity_name,
                "amount": float(a.amount),
                "expected_delivery_date": str(a.due_or_disbursed_date),
                "days_overdue": a.days_overdue,
                "severity_score": float(a.severity_score),
                "evidence": a.evidence_summary,
                "suggested_action": a.suggested_action
            }
            for a in advances
        ]

    def get_bounced_cheques_tool(self, business_id: uuid.UUID, as_of: date) -> List[Dict[str, Any]]:
        """Identifies bounced customer cheques creating phantom cash exposure."""
        bounced = self.cash_engine.calculate_bounced_cheque_exposure(business_id=business_id, as_of=as_of)
        return [
            {
                "blockage_id": b.blockage_id,
                "counterparty": b.entity_name,
                "amount": float(b.amount),
                "cheque_date": str(b.due_or_disbursed_date),
                "days_since_bounce": b.days_overdue,
                "severity_score": float(b.severity_score),
                "evidence": b.evidence_summary
            }
            for b in bounced
        ]

    def project_cash_flow_tool(self, business_id: uuid.UUID, as_of: date, horizon_days: int = 30) -> Dict[str, Any]:
        """Calculates forward daily cash trajectory and pinpoints deficit dates."""
        projection = self.cash_engine.project_cash_flow(business_id=business_id, as_of=as_of, window_days=horizon_days)
        return {
            "as_of_date": str(projection.as_of_date),
            "starting_cash": float(projection.starting_liquid_cash),
            "forecast_horizon_days": projection.forecast_horizon_days,
            "first_deficit_date": str(projection.first_deficit_date) if projection.first_deficit_date else None,
            "max_deficit_amount": float(projection.max_deficit_amount),
            "total_expected_inflows": float(projection.total_expected_inflows),
            "total_committed_outflows": float(projection.total_committed_outflows),
            "daily_forecasts": [
                {
                    "date": str(df.forecast_date),
                    "day_offset": df.day_offset,
                    "opening": float(df.opening_balance),
                    "inflows": float(df.expected_inflows),
                    "outflows": float(df.committed_outflows),
                    "closing": float(df.closing_balance),
                    "has_deficit": df.has_deficit
                }
                for df in projection.daily_forecasts
            ]
        }

    def trace_contagion_paths_tool(self, business_id: uuid.UUID, as_of: date, horizon_days: int = 15) -> List[Dict[str, Any]]:
        """Maps causal links from overdue customer receivables to threatened liabilities."""
        return self.contagion_engine.trace_receivable_to_obligation_paths(
            business_id=business_id,
            as_of=as_of,
            horizon_days=horizon_days
        )

    def get_concentration_tool(self, business_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Calculates counterparty concentration risk of blocked working capital."""
        return self.contagion_engine.find_top_counterparty_concentrations(business_id=business_id)
