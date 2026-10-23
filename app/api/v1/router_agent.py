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


@router.get("/llm-health", summary="Diagnose Live LLM Model Providers")
def check_llm_providers_health():
    """
    Directly tests network connectivity, credentials, and live generation
    across all configured LLM providers (OpenRouter, Gemini, Hugging Face).
    Returns real-time status, latency in milliseconds, and raw responses.
    """
    import time
    from app.core.config import settings
    from app.agent.llm_client import MultiProviderLLMClient

    client = MultiProviderLLMClient()
    results = {}

    test_system = "You are a test assistant."
    test_prompt = "Reply with exactly: OK"

    # 1. Test OpenRouter
    or_start = time.time()
    try:
        or_text = client._call_openrouter(test_system, test_prompt)
        results["openrouter"] = {
            "status": "ONLINE",
            "model": settings.OPENROUTER_MODEL,
            "latency_ms": round((time.time() - or_start) * 1000, 2),
            "response": or_text[:100]
        }
    except Exception as exc:
        results["openrouter"] = {
            "status": "OFFLINE_OR_ERROR",
            "model": settings.OPENROUTER_MODEL,
            "latency_ms": round((time.time() - or_start) * 1000, 2),
            "error": str(exc)
        }

    # 2. Test Gemini
    gem_start = time.time()
    try:
        gem_text = client._call_gemini(test_system, test_prompt)
        results["gemini"] = {
            "status": "ONLINE",
            "model": settings.GEMINI_MODEL,
            "latency_ms": round((time.time() - gem_start) * 1000, 2),
            "response": gem_text[:100]
        }
    except Exception as exc:
        results["gemini"] = {
            "status": "OFFLINE_OR_ERROR",
            "model": settings.GEMINI_MODEL,
            "latency_ms": round((time.time() - gem_start) * 1000, 2),
            "error": str(exc)
        }

    # 3. Test Hugging Face
    hf_start = time.time()
    try:
        hf_text = client._call_huggingface(test_system, test_prompt)
        results["huggingface"] = {
            "status": "ONLINE",
            "model": settings.HUGGINGFACE_MODEL,
            "latency_ms": round((time.time() - hf_start) * 1000, 2),
            "response": hf_text[:100]
        }
    except Exception as exc:
        results["huggingface"] = {
            "status": "OFFLINE_OR_ERROR",
            "model": settings.HUGGINGFACE_MODEL,
            "latency_ms": round((time.time() - hf_start) * 1000, 2),
            "error": str(exc)
        }

    # 4. Deterministic Rule-Based Grounded Fallback
    results["grounded_fallback"] = {
        "status": "ONLINE_GUARANTEED",
        "model": "rule_based_evidence_synthesizer",
        "latency_ms": 0.5,
        "description": "Zero-hallucination deterministic template synthesizer citing canonical records."
    }

    return results
