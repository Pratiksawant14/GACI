"""
Graph Contagion and Path-Tracing Intelligence Engine.
Traces causal paths from overdue receivables to impending obligations,
calculates party concentration risk, and extracts subgraphs for visualization.
Supports direct Neo4j Cypher traversal with fallback to in-memory NetworkX projection.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
import networkx as nx
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.graph.client import Neo4jClient, neo4j_client
from app.services.projection_service import ProjectionService
from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import SalesInvoice, Payment, SupplierAdvance, FinancialObligation


class ContagionPath(dict):
    """Structured representation of a causal liquidity contagion path."""
    pass


class GraphContagionEngine:
    """Graph traversal and topological analysis engine for cash contagion."""

    def __init__(self, session: Session, graph_client: Neo4jClient = neo4j_client):
        self.session = session
        self.client = graph_client
        self.projection_service = ProjectionService(session, graph_client)

    def trace_receivable_to_obligation_paths(
        self,
        business_id: uuid.UUID,
        as_of: date,
        horizon_days: int = 15
    ) -> List[Dict[str, Any]]:
        """Traces paths connecting overdue customer receivables to impending obligations."""
        if self.client and self.client.verify_connectivity():
            try:
                cypher = """
                MATCH (c:Customer)-[:ISSUED_INVOICE]->(i:Invoice)
                WHERE i.status = 'OVERDUE' AND i.business_id = $biz_id
                MATCH (b:Business {id: $biz_id})-[:COMMITTED_TO]->(o:Obligation)
                WHERE o.status = 'SCHEDULED' AND o.due_date <= date($horizon_date)
                OPTIONAL MATCH (o)-[:PAYABLE_FROM]->(ba:BankAccount)
                RETURN c.name AS customer_name,
                       i.invoice_number AS invoice_number,
                       i.unpaid_balance AS invoice_unpaid,
                       i.due_date AS invoice_due_date,
                       o.name AS obligation_name,
                       o.category AS obligation_category,
                       o.amount AS obligation_amount,
                       o.due_date AS obligation_due_date,
                       ba.name AS bank_name
                ORDER BY o.due_date ASC, i.unpaid_balance DESC
                LIMIT 20
                """
                horizon_date = as_of + timedelta(days=horizon_days)
                records = self.client.execute_query(cypher, {
                    "biz_id": str(business_id),
                    "horizon_date": str(horizon_date)
                })
                return records
            except Exception as exc:
                logger.warning(f"Neo4j Cypher contagion trace failed, using in-memory graph: {exc}")

        # Fallback to in-memory graph traversal via NetworkX / Relational models
        return self._trace_contagion_relational(business_id, as_of, horizon_days)

    def _trace_contagion_relational(
        self,
        business_id: uuid.UUID,
        as_of: date,
        horizon_days: int
    ) -> List[Dict[str, Any]]:
        """Relational / in-memory path tracing fallback."""
        horizon_date = as_of + timedelta(days=horizon_days)

        # Overdue invoices
        inv_stmt = select(SalesInvoice).where(
            SalesInvoice.business_id == business_id,
            SalesInvoice.due_date < as_of,
            SalesInvoice.paid_amount < SalesInvoice.total_amount,
            SalesInvoice.status.notin_(["CANCELLED", "PAID"])
        ).order_by((SalesInvoice.total_amount - SalesInvoice.paid_amount).desc())
        overdue_invoices = list(self.session.scalars(inv_stmt).all())

        # Impending obligations
        ob_stmt = select(FinancialObligation).where(
            FinancialObligation.business_id == business_id,
            FinancialObligation.due_date >= as_of,
            FinancialObligation.due_date <= horizon_date,
            FinancialObligation.status == "SCHEDULED"
        ).order_by(FinancialObligation.due_date.asc())
        impending_obligations = list(self.session.scalars(ob_stmt).all())

        paths: List[Dict[str, Any]] = []
        for ob in impending_obligations:
            bank_name = ob.bank_account.account_name if ob.bank_account else "Unallocated Account"
            for inv in overdue_invoices:
                paths.append({
                    "customer_name": inv.customer.name if inv.customer else "Customer",
                    "invoice_number": inv.invoice_number,
                    "invoice_unpaid": float(inv.unpaid_balance),
                    "invoice_due_date": str(inv.due_date),
                    "obligation_name": ob.obligation_name,
                    "obligation_category": ob.category,
                    "obligation_amount": float(ob.amount),
                    "obligation_due_date": str(ob.due_date),
                    "bank_name": bank_name,
                    "causal_link": (
                        f"Delayed receipt of {inv.unpaid_balance} from {inv.customer.name if inv.customer else 'Customer'} "
                        f"(Invoice {inv.invoice_number}) contributes directly to cash shortfall for {ob.obligation_name} "
                        f"({ob.amount}) due on {ob.due_date}."
                    )
                })

        return paths

    def find_top_counterparty_concentrations(self, business_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Calculates counterparty concentration risk of blocked working capital."""
        inv_stmt = select(
            Customer.name,
            func.sum(SalesInvoice.total_amount - SalesInvoice.paid_amount).label("blocked_total"),
            func.count(SalesInvoice.id).label("invoice_count")
        ).join(Customer, Customer.id == SalesInvoice.customer_id).where(
            SalesInvoice.business_id == business_id,
            SalesInvoice.paid_amount < SalesInvoice.total_amount,
            SalesInvoice.status.notin_(["CANCELLED", "PAID"])
        ).group_by(Customer.name).order_by(func.sum(SalesInvoice.total_amount - SalesInvoice.paid_amount).desc())

        results = self.session.execute(inv_stmt).all()
        total_blocked = sum((r[1] for r in results), Decimal("0.00"))

        concentrations = []
        for r in results:
            amount = Decimal(str(r[1]))
            pct = (amount / total_blocked * Decimal("100.0")).quantize(Decimal("0.1")) if total_blocked > 0 else Decimal("0.0")
            concentrations.append({
                "customer_name": r[0],
                "blocked_amount": float(amount),
                "invoice_count": r[2],
                "concentration_percentage": float(pct)
            })

        return concentrations

    def get_entity_subgraph(
        self,
        business_id: uuid.UUID,
        center_node_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extracts nodes and edges for PyVis visualization."""
        G = self.projection_service.build_networkx_graph(business_id=business_id)

        nodes_data = []
        for node_id, attrs in G.nodes(data=True):
            node_type = attrs.get("type", "Unknown")
            label = attrs.get("name") or attrs.get("ref") or node_id
            nodes_data.append({
                "id": node_id,
                "label": label,
                "type": node_type,
                "properties": {k: v for k, v in attrs.items() if k not in ["type", "name", "ref"]}
            })

        edges_data = []
        for u, v, attrs in G.edges(data=True):
            edges_data.append({
                "from": u,
                "to": v,
                "relation": attrs.get("relation", "CONNECTED_TO"),
                "amount": attrs.get("amount") or attrs.get("value")
            })

        return {
            "nodes": nodes_data,
            "edges": edges_data,
            "total_nodes": len(nodes_data),
            "total_edges": len(edges_data)
        }
