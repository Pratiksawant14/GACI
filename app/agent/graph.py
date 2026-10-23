"""
LangGraph Cash-Flow Intelligence Agent State Machine.
Implements the 4-stage diagnostic pipeline:
1. Intent Analyzer -> 2. Tool Executor -> 3. Evidence Validator -> 4. Grounded Response Generator
"""

import uuid
from datetime import date, datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, START, END

from app.agent.state import AgentState, AgentCitation
from app.agent.tools import AgentToolSuite
from app.agent.prompts import AGENT_SYSTEM_PROMPT, build_analysis_prompt
from app.agent.llm_client import MultiProviderLLMClient, multi_llm_client
from app.core.logging import logger


def classify_intent(query: str) -> str:
    """Classifies user query into primary financial diagnostic intent."""
    q = query.lower()
    if any(k in q for k in ["contagion", "spillover", "emi", "gst", "tax", "payroll", "default", "can i pay", "chain reaction"]):
        return "contagion"
    elif any(k in q for k in ["stuck", "blocked", "overdue", "stranded", "advance", "cheque", "bounce", "aging"]):
        return "blockage"
    elif any(k in q for k in ["forecast", "projection", "run out", "deficit", "shortfall", "next 15", "next 30"]):
        return "forecast"
    elif any(k in q for k in ["concentration", "top customer", "top supplier", "exposure", "ratio"]):
        return "concentration"
    elif any(k in q for k in ["summary", "balance", "liquid", "how much", "status", "overview"]):
        return "summary"
    return "comprehensive"


class CashFlowAgentWorkflow:
    """Orchestrates LangGraph state graph for wholesale cash-flow intelligence."""

    def __init__(self, db: Session, llm_client: Optional[MultiProviderLLMClient] = None):
        self.db = db
        self.tools = AgentToolSuite(db)
        self.llm = llm_client or multi_llm_client
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)

        # Register nodes
        builder.add_node("intent_analyzer", self._intent_analyzer_node)
        builder.add_node("tool_executor", self._tool_executor_node)
        builder.add_node("evidence_validator", self._evidence_validator_node)
        builder.add_node("response_generator", self._response_generator_node)

        # Register edges
        builder.add_edge(START, "intent_analyzer")
        builder.add_edge("intent_analyzer", "tool_executor")
        builder.add_edge("tool_executor", "evidence_validator")
        builder.add_edge("evidence_validator", "response_generator")
        builder.add_edge("response_generator", END)

        return builder.compile()

    def _intent_analyzer_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 1: Classifies diagnostic intent."""
        intent = classify_intent(state["query"])
        logger.info(f"Agent Intent Analyzer: query='{state['query']}' -> intent='{intent}'")
        return {"intent": intent}

    def _tool_executor_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 2: Executes deterministic tools corresponding to classified intent."""
        biz_id = uuid.UUID(state["business_id"])
        as_of = date.fromisoformat(state["as_of"])
        intent = state.get("intent", "comprehensive")

        tool_outputs = {}

        # Base financial summary is always gathered
        tool_outputs["summary"] = self.tools.get_cash_summary_tool(biz_id, as_of)

        # Conditional tool executions
        if intent in ("blockage", "comprehensive", "contagion"):
            tool_outputs["overdue_receivables"] = self.tools.get_overdue_receivables_tool(biz_id, as_of)
            tool_outputs["stranded_advances"] = self.tools.get_stranded_advances_tool(biz_id, as_of)
            tool_outputs["bounced_cheques"] = self.tools.get_bounced_cheques_tool(biz_id, as_of)

        if intent in ("contagion", "comprehensive"):
            tool_outputs["contagion_paths"] = self.tools.trace_contagion_paths_tool(biz_id, as_of, horizon_days=15)

        if intent in ("forecast", "comprehensive"):
            tool_outputs["projection"] = self.tools.project_cash_flow_tool(biz_id, as_of, horizon_days=30)

        if intent in ("concentration", "comprehensive"):
            tool_outputs["concentrations"] = self.tools.get_concentration_tool(biz_id)

        return {"tool_outputs": tool_outputs}

    def _evidence_validator_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 3: Validates figures and builds grounded canonical citations."""
        raw = state.get("tool_outputs", {})
        citations: List[AgentCitation] = []
        validated: Dict[str, Any] = {}

        # 1. Summary
        if "summary" in raw:
            validated["summary"] = raw["summary"]

        # 2. Blockages & Citations
        blockage_list = []
        for r in raw.get("overdue_receivables", []):
            blockage_list.append(r)
            citations.append({
                "record_type": "SalesInvoice",
                "identifier": r.get("blockage_id", "N/A"),
                "counterparty": r.get("customer_name", "N/A"),
                "amount": r.get("amount", 0.0),
                "status": f"Overdue {r.get('days_overdue', 0)} days",
                "details": r.get("evidence", "")
            })

        for a in raw.get("stranded_advances", []):
            blockage_list.append(a)
            citations.append({
                "record_type": "SupplierAdvance",
                "identifier": a.get("blockage_id", "N/A"),
                "counterparty": a.get("supplier_name", "N/A"),
                "amount": a.get("amount", 0.0),
                "status": f"Delivery overdue {a.get('days_overdue', 0)} days",
                "details": a.get("evidence", "")
            })

        for chq in raw.get("bounced_cheques", []):
            blockage_list.append(chq)
            citations.append({
                "record_type": "Payment",
                "identifier": chq.get("blockage_id", "N/A"),
                "counterparty": chq.get("counterparty", "N/A"),
                "amount": chq.get("amount", 0.0),
                "status": "BOUNCED",
                "details": chq.get("evidence", "")
            })

        validated["blockages"] = blockage_list
        validated["contagion_paths"] = raw.get("contagion_paths", [])
        validated["projection"] = raw.get("projection", {})
        validated["concentrations"] = raw.get("concentrations", [])

        # Add obligation citations from contagion paths
        for path in validated["contagion_paths"]:
            citations.append({
                "record_type": "FinancialObligation",
                "identifier": path.get("obligation_name", "Obligation"),
                "counterparty": path.get("obligation_category", "Liability"),
                "amount": path.get("obligation_amount", 0.0),
                "status": f"Due on {path.get('obligation_due_date', '')}",
                "details": path.get("causal_link", "")
            })

        return {"validated_evidence": validated, "citations": citations}

    def _response_generator_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 4: Generates grounded plain-language answer citing canonical records."""
        user_prompt = build_analysis_prompt(state["query"], state.get("validated_evidence", {}))
        gen_result = self.llm.generate(
            system_prompt=AGENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            evidence=state.get("validated_evidence", {})
        )

        return {
            "final_response": gen_result["text"],
            "provider_used": gen_result["provider"],
            "latency_ms": gen_result.get("latency_ms", 0.0)
        }

    def execute(self, query: str, business_id: uuid.UUID, as_of: Optional[date] = None) -> AgentState:
        """Executes full diagnostic workflow and returns final state."""
        ref_date = as_of or date.today()
        initial_state: AgentState = {
            "query": query,
            "business_id": str(business_id),
            "as_of": ref_date.isoformat(),
            "intent": "comprehensive",
            "tool_outputs": {},
            "validated_evidence": {},
            "citations": [],
            "final_response": "",
            "provider_used": "",
            "latency_ms": 0.0
        }

        final_state = self.graph.invoke(initial_state)
        return final_state
