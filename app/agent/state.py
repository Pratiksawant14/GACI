"""
LangGraph Agent State Definitions.
Defines typed state schemas for the multi-step explainability pipeline.
"""

import uuid
from datetime import date
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict


class AgentCitation(TypedDict):
    record_type: str
    identifier: str
    counterparty: str
    amount: float
    status: str
    details: str


class AgentState(TypedDict):
    """Execution state passed through the LangGraph diagnostic pipeline."""
    query: str
    business_id: str
    as_of: str
    intent: str
    tool_outputs: Dict[str, Any]
    validated_evidence: Dict[str, Any]
    citations: List[AgentCitation]
    final_response: str
    provider_used: str
    latency_ms: float
