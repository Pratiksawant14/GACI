"""
Graph Projection and Synchronization Service.
Projects canonical relational database records into the Neo4j Temporal Business Graph.
Also provides an in-memory NetworkX projection graph for fast topological traversal and offline execution.
"""

import uuid
from typing import Dict, Any, Optional
import networkx as nx
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.logging import logger
from app.graph.client import Neo4jClient, neo4j_client
from app.graph import cypher_queries as cq
from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import (
    SalesInvoice,
    Payment,
    PaymentAllocation,
    SupplierAdvance,
    Delivery,
    FinancialObligation
)


class ProjectionService:
    """Synchronizes canonical relational records to Neo4j and NetworkX business graphs."""

    def __init__(self, session: Session, graph_client: Neo4jClient = neo4j_client):
        self.session = session
        self.client = graph_client

    def sync_all(self, business_id: Optional[uuid.UUID] = None) -> Dict[str, int]:
        """Performs full idempotent graph projection of all canonical records."""
        counts = {
            "businesses": 0,
            "customers": 0,
            "suppliers": 0,
            "bank_accounts": 0,
            "invoices": 0,
            "payments": 0,
            "advances": 0,
            "deliveries": 0,
            "obligations": 0
        }

        # 1. Businesses
        biz_stmt = select(Business)
        if business_id:
            biz_stmt = biz_stmt.where(Business.id == business_id)
        businesses = list(self.session.scalars(biz_stmt).all())
        for b in businesses:
            self._project_business(b)
            counts["businesses"] += 1

        # 2. Customers & Suppliers
        cust_stmt = select(Customer)
        sup_stmt = select(Supplier)
        bank_stmt = select(BankAccount)
        if business_id:
            cust_stmt = cust_stmt.where(Customer.business_id == business_id)
            sup_stmt = sup_stmt.where(Supplier.business_id == business_id)
            bank_stmt = bank_stmt.where(BankAccount.business_id == business_id)

        for c in self.session.scalars(cust_stmt).all():
            self._project_customer(c)
            counts["customers"] += 1

        for s in self.session.scalars(sup_stmt).all():
            self._project_supplier(s)
            counts["suppliers"] += 1

        for a in self.session.scalars(bank_stmt).all():
            self._project_bank_account(a)
            counts["bank_accounts"] += 1

        # 3. Invoices
        inv_stmt = select(SalesInvoice)
        if business_id:
            inv_stmt = inv_stmt.where(SalesInvoice.business_id == business_id)
        for inv in self.session.scalars(inv_stmt).all():
            self._project_invoice(inv)
            counts["invoices"] += 1

        # 4. Payments & Allocations
        pmt_stmt = select(Payment)
        if business_id:
            pmt_stmt = pmt_stmt.where(Payment.business_id == business_id)
        for pmt in self.session.scalars(pmt_stmt).all():
            self._project_payment(pmt)
            counts["payments"] += 1

        # 5. Advances & Deliveries
        adv_stmt = select(SupplierAdvance)
        deliv_stmt = select(Delivery)
        ob_stmt = select(FinancialObligation)
        if business_id:
            adv_stmt = adv_stmt.where(SupplierAdvance.business_id == business_id)
            deliv_stmt = deliv_stmt.where(Delivery.business_id == business_id)
            ob_stmt = ob_stmt.where(FinancialObligation.business_id == business_id)

        for adv in self.session.scalars(adv_stmt).all():
            self._project_advance(adv)
            counts["advances"] += 1

        for d in self.session.scalars(deliv_stmt).all():
            self._project_delivery(d)
            counts["deliveries"] += 1

        for o in self.session.scalars(ob_stmt).all():
            self._project_obligation(o)
            counts["obligations"] += 1

        logger.info(f"Full graph projection completed: {counts}")
        return counts

    def _safe_write(self, cypher: str, params: Dict[str, Any]):
        """Executes a write query to Neo4j if reachable."""
        try:
            if self.client and self.client.verify_connectivity():
                self.client.execute_write(cypher, params)
        except Exception as exc:
            logger.warning(f"Neo4j write skipped / unavailable: {exc}")

    def _project_business(self, b: Business):
        params = {"id": str(b.id), "name": b.name, "currency": b.currency}
        self._safe_write(cq.MERGE_BUSINESS, params)

    def _project_customer(self, c: Customer):
        params = {"id": str(c.id), "name": c.name, "credit_limit": float(c.credit_limit), "business_id": str(c.business_id)}
        self._safe_write(cq.MERGE_CUSTOMER, params)

    def _project_supplier(self, s: Supplier):
        params = {"id": str(s.id), "name": s.name, "business_id": str(s.business_id)}
        self._safe_write(cq.MERGE_SUPPLIER, params)

    def _project_bank_account(self, a: BankAccount):
        params = {
            "id": str(a.id),
            "account_name": a.account_name,
            "account_type": a.account_type,
            "current_balance": float(a.current_balance),
            "business_id": str(a.business_id)
        }
        self._safe_write(cq.MERGE_BANK_ACCOUNT, params)

    def _project_invoice(self, inv: SalesInvoice):
        params = {
            "id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "total_amount": float(inv.total_amount),
            "paid_amount": float(inv.paid_amount),
            "unpaid_balance": float(inv.unpaid_balance),
            "issue_date": str(inv.issue_date),
            "due_date": str(inv.due_date),
            "status": inv.status,
            "business_id": str(inv.business_id),
            "customer_id": str(inv.customer_id)
        }
        self._safe_write(cq.MERGE_INVOICE, params)
        self._safe_write(cq.LINK_CUSTOMER_INVOICE, {"customer_id": str(inv.customer_id), "invoice_id": str(inv.id)})

    def _project_payment(self, p: Payment):
        params = {
            "id": str(p.id),
            "payment_reference": p.payment_reference,
            "amount": float(p.amount),
            "payment_date": str(p.payment_date),
            "payment_method": p.payment_method,
            "status": p.status,
            "business_id": str(p.business_id),
            "bank_account_id": str(p.bank_account_id)
        }
        self._safe_write(cq.MERGE_PAYMENT, params)
        self._safe_write(cq.LINK_PAYMENT_BANK, {"payment_id": str(p.id), "bank_account_id": str(p.bank_account_id)})

        if p.customer_id:
            self._safe_write(cq.LINK_CUSTOMER_PAYMENT, {"customer_id": str(p.customer_id), "payment_id": str(p.id)})

        # Allocations
        for alloc in p.allocations:
            alloc_params = {
                "payment_id": str(p.id),
                "invoice_id": str(alloc.invoice_id),
                "allocated_amount": float(alloc.allocated_amount)
            }
            self._safe_write(cq.LINK_PAYMENT_INVOICE, alloc_params)

    def _project_advance(self, adv: SupplierAdvance):
        params = {
            "id": str(adv.id),
            "advance_reference": adv.advance_reference,
            "advance_amount": float(adv.advance_amount),
            "fulfilled_amount": float(adv.fulfilled_amount),
            "unfulfilled_balance": float(adv.unfulfilled_balance),
            "disbursement_date": str(adv.disbursement_date),
            "expected_delivery_date": str(adv.expected_delivery_date),
            "status": adv.status,
            "business_id": str(adv.business_id),
            "supplier_id": str(adv.supplier_id)
        }
        self._safe_write(cq.MERGE_SUPPLIER_ADVANCE, params)
        self._safe_write(cq.LINK_BUSINESS_ADVANCE, {"business_id": str(adv.business_id), "advance_id": str(adv.id)})
        self._safe_write(cq.LINK_ADVANCE_SUPPLIER, {"advance_id": str(adv.id), "supplier_id": str(adv.supplier_id)})

    def _project_delivery(self, d: Delivery):
        params = {
            "id": str(d.id),
            "delivery_reference": d.delivery_reference,
            "delivery_date": str(d.delivery_date),
            "delivered_value": float(d.delivered_value),
            "business_id": str(d.business_id),
            "supplier_id": str(d.supplier_id)
        }
        self._safe_write(cq.MERGE_DELIVERY, params)
        if d.advance_id:
            self._safe_write(cq.LINK_DELIVERY_ADVANCE, {"delivery_id": str(d.id), "advance_id": str(d.advance_id)})

    def _project_obligation(self, o: FinancialObligation):
        params = {
            "id": str(o.id),
            "obligation_name": o.obligation_name,
            "category": o.category,
            "amount": float(o.amount),
            "due_date": str(o.due_date),
            "status": o.status,
            "business_id": str(o.business_id)
        }
        self._safe_write(cq.MERGE_OBLIGATION, params)
        self._safe_write(cq.LINK_BUSINESS_OBLIGATION, {"business_id": str(o.business_id), "obligation_id": str(o.id)})
        if o.bank_account_id:
            self._safe_write(cq.LINK_OBLIGATION_BANK, {"obligation_id": str(o.id), "bank_account_id": str(o.bank_account_id)})

    def build_networkx_graph(self, business_id: Optional[uuid.UUID] = None) -> nx.DiGraph:
        """Constructs an in-memory directed NetworkX graph representing the temporal business network."""
        G = nx.DiGraph()

        # Load relational entities
        biz_stmt = select(Business)
        if business_id:
            biz_stmt = biz_stmt.where(Business.id == business_id)

        for b in self.session.scalars(biz_stmt).all():
            G.add_node(f"business_{b.id}", type="Business", name=b.name, currency=b.currency)

        cust_stmt = select(Customer)
        sup_stmt = select(Supplier)
        bank_stmt = select(BankAccount)
        inv_stmt = select(SalesInvoice)
        pmt_stmt = select(Payment)
        adv_stmt = select(SupplierAdvance)
        deliv_stmt = select(Delivery)
        ob_stmt = select(FinancialObligation)

        if business_id:
            cust_stmt = cust_stmt.where(Customer.business_id == business_id)
            sup_stmt = sup_stmt.where(Supplier.business_id == business_id)
            bank_stmt = bank_stmt.where(BankAccount.business_id == business_id)
            inv_stmt = inv_stmt.where(SalesInvoice.business_id == business_id)
            pmt_stmt = pmt_stmt.where(Payment.business_id == business_id)
            adv_stmt = adv_stmt.where(SupplierAdvance.business_id == business_id)
            deliv_stmt = deliv_stmt.where(Delivery.business_id == business_id)
            ob_stmt = ob_stmt.where(FinancialObligation.business_id == business_id)

        for c in self.session.scalars(cust_stmt).all():
            G.add_node(f"customer_{c.id}", type="Customer", name=c.name, credit_limit=float(c.credit_limit))

        for s in self.session.scalars(sup_stmt).all():
            G.add_node(f"supplier_{s.id}", type="Supplier", name=s.name)

        for a in self.session.scalars(bank_stmt).all():
            G.add_node(f"bank_{a.id}", type="BankAccount", name=a.account_name, balance=float(a.current_balance))

        for inv in self.session.scalars(inv_stmt).all():
            node_id = f"invoice_{inv.id}"
            G.add_node(
                node_id,
                type="Invoice",
                ref=inv.invoice_number,
                amount=float(inv.total_amount),
                unpaid_balance=float(inv.unpaid_balance),
                status=inv.status,
                due_date=str(inv.due_date)
            )
            G.add_edge(f"customer_{inv.customer_id}", node_id, relation="ISSUED_INVOICE")

        for p in self.session.scalars(pmt_stmt).all():
            node_id = f"payment_{p.id}"
            G.add_node(node_id, type="Payment", ref=p.payment_reference, amount=float(p.amount), status=p.status)
            G.add_edge(node_id, f"bank_{p.bank_account_id}", relation="DEPOSITED_IN")
            if p.customer_id:
                G.add_edge(f"customer_{p.customer_id}", node_id, relation="MADE_PAYMENT")
            for alloc in p.allocations:
                G.add_edge(node_id, f"invoice_{alloc.invoice_id}", relation="ALLOCATED_TO", amount=float(alloc.allocated_amount))

        for adv in self.session.scalars(adv_stmt).all():
            node_id = f"advance_{adv.id}"
            G.add_node(
                node_id,
                type="SupplierAdvance",
                ref=adv.advance_reference,
                amount=float(adv.advance_amount),
                unfulfilled_balance=float(adv.unfulfilled_balance),
                expected_delivery_date=str(adv.expected_delivery_date),
                status=adv.status
            )
            G.add_edge(f"business_{adv.business_id}", node_id, relation="DISBURSED_ADVANCE")
            G.add_edge(node_id, f"supplier_{adv.supplier_id}", relation="PAID_TO")

        for d in self.session.scalars(deliv_stmt).all():
            node_id = f"delivery_{d.id}"
            G.add_node(node_id, type="Delivery", ref=d.delivery_reference, value=float(d.delivered_value))
            if d.advance_id:
                G.add_edge(node_id, f"advance_{d.advance_id}", relation="FULFILLS")

        for o in self.session.scalars(ob_stmt).all():
            node_id = f"obligation_{o.id}"
            G.add_node(node_id, type="Obligation", name=o.obligation_name, category=o.category, amount=float(o.amount), due_date=str(o.due_date), status=o.status)
            G.add_edge(f"business_{o.business_id}", node_id, relation="COMMITTED_TO")
            if o.bank_account_id:
                G.add_edge(node_id, f"bank_{o.bank_account_id}", relation="PAYABLE_FROM")

        return G
