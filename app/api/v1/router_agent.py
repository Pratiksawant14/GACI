"""
Agent Explainability Q&A REST Endpoints.
Exposes the LangGraph multi-step diagnostic workflow for conversational cash-flow intelligence.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_active_business
from app.models.entities import Business
from app.agent.graph import CashFlowAgentWorkflow
from app.core.logging import logger

router = APIRouter(prefix="/agent", tags=["Agent"])


class AgentQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Natural language question about cash-flow, blockages, or liabilities")
    as_of: Optional[date] = Field(default=None, description="Reference date for calculations")
    business_id: Optional[uuid.UUID] = Field(default=None, description="Optional Business UUID")


class AgentQueryResponse(BaseModel):
    query: str
    intent: str
    answer: str
    citations: List[Dict[str, Any]]
    evidence: Dict[str, Any]
    provider_used: str
    latency_ms: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@router.post("/query", response_model=AgentQueryResponse, summary="Query Cash-Flow Intelligence Agent")
def query_agent(
    req: AgentQueryRequest,
    business: Business = Depends(get_active_business),
    db: Session = Depends(get_db)
) -> AgentQueryResponse:
    """
    Executes the 4-step LangGraph explainability pipeline:
    1. Analyzes intent
    2. Runs deterministic financial & graph tools
    3. Validates evidence & builds canonical record citations
    4. Synthesizes a grounded plain-language answer citing database facts.
    """
    logger.info(f"Agent Query received: '{req.query}' for business {business.id}")
    workflow = CashFlowAgentWorkflow(db=db)
    final_state = workflow.execute(
        query=req.query,
        business_id=business.id,
        as_of=req.as_of
    )

    return AgentQueryResponse(
        query=req.query,
        intent=final_state["intent"],
        answer=final_state["final_response"],
        citations=final_state["citations"],
        evidence=final_state["validated_evidence"],
        provider_used=final_state["provider_used"],
        latency_ms=final_state["latency_ms"]
    )
