"""
Unit Tests for Agent Deterministic Tools and MultiProviderLLMClient (TSK-16).
Verifies that agent tools return exact figures, and that multi-provider failover
cascades gracefully to deterministic synthesis without errors.
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch, MagicMock
import pytest

from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import SalesInvoice, SupplierAdvance, Payment, FinancialObligation
from app.agent.tools import AgentToolSuite
from app.agent.llm_client import MultiProviderLLMClient
from app.agent.graph import classify_intent


def test_intent_classification():
    """Verifies intent analyzer rules."""
    assert classify_intent("Why is cash stuck?") == "blockage"
    assert classify_intent("Can I pay my upcoming loan EMI and GST?") == "contagion"
    assert classify_intent("Give me a 30 day cash projection and deficit forecast") == "forecast"
    assert classify_intent("What is my top customer concentration risk?") == "concentration"
    assert classify_intent("What is our current liquid cash balance summary?") == "summary"
    assert classify_intent("Give me a complete financial checkup") == "comprehensive"


def test_agent_tools_data_extraction(db_session):
    """Verifies that AgentToolSuite extracts grounded database records accurately."""
    biz = Business(name="Agent Tools Test Biz", currency="INR")
    db_session.add(biz)
    db_session.flush()

    bank = BankAccount(business_id=biz.id, account_name="Checking", current_balance=Decimal("150000.00"))
    cust = Customer(business_id=biz.id, name="Omega Stores")
    supp = Supplier(business_id=biz.id, name="Alpha Mills")
    db_session.add_all([bank, cust, supp])
    db_session.flush()

    # Overdue invoice
    inv = SalesInvoice(
        business_id=biz.id,
        customer_id=cust.id,
        invoice_number="INV-TOOL-01",
        issue_date=date(2026, 9, 1),
        due_date=date(2026, 9, 20),
        total_amount=Decimal("60000.00"),
        paid_amount=Decimal("10000.00"),
        status="OVERDUE"
    )
    # Stranded advance
    adv = SupplierAdvance(
        business_id=biz.id,
        supplier_id=supp.id,
        bank_account_id=bank.id,
        advance_reference="ADV-TOOL-01",
        disbursement_date=date(2026, 9, 5),
        expected_delivery_date=date(2026, 9, 15),
        advance_amount=Decimal("40000.00"),
        fulfilled_amount=Decimal("0.00"),
        status="DISBURSED"
    )
    # Bounced cheque
    pmt = Payment(
        business_id=biz.id,
        bank_account_id=bank.id,
        customer_id=cust.id,
        payment_reference="PMT-BOUNCE-01",
        payment_date=date(2026, 10, 5),
        amount=Decimal("25000.00"),
        payment_method="CHEQUE",
        status="BOUNCED"
    )
    # Scheduled obligation
    ob = FinancialObligation(
        business_id=biz.id,
        bank_account_id=bank.id,
        obligation_name="Factory Rent",
        category="RENT",
        due_date=date(2026, 10, 27),
        amount=Decimal("45000.00"),
        status="SCHEDULED"
    )
    db_session.add_all([inv, adv, pmt, ob])
    db_session.commit()

    suite = AgentToolSuite(db_session)
    as_of = date(2026, 10, 23)

    # 1. Cash Summary Tool
    summary = suite.get_cash_summary_tool(biz.id, as_of)
    assert summary["liquid_cash"] == 150000.00
    assert summary["total_overdue_receivables"] == 50000.00
    assert summary["total_stranded_advances"] == 40000.00
    assert summary["bounced_cheque_exposure"] == 25000.00
    assert summary["upcoming_obligations_15d"] == 45000.00

    # 2. Overdue Receivables Tool
    overdue = suite.get_overdue_receivables_tool(biz.id, as_of)
    assert len(overdue) == 1
    assert overdue[0]["customer_name"] == "Omega Stores"
    assert overdue[0]["amount"] == 50000.00
    assert overdue[0]["days_overdue"] == 33

    # 3. Stranded Advances Tool
    advances = suite.get_stranded_advances_tool(biz.id, as_of)
    assert len(advances) == 1
    assert advances[0]["supplier_name"] == "Alpha Mills"
    assert advances[0]["amount"] == 40000.00

    # 4. Bounced Cheques Tool
    bounced = suite.get_bounced_cheques_tool(biz.id, as_of)
    assert len(bounced) == 1
    assert bounced[0]["counterparty"] == "Omega Stores"
    assert bounced[0]["amount"] == 25000.00

    # 5. Contagion Paths Tool
    paths = suite.trace_contagion_paths_tool(biz.id, as_of, horizon_days=15)
    assert len(paths) >= 1
    assert paths[0]["customer_name"] == "Omega Stores"
    assert paths[0]["obligation_name"] == "Factory Rent"


def test_multi_provider_llm_fallback():
    """Verifies automatic failover from OpenRouter -> Gemini -> Hugging Face -> Deterministic synthesizer."""
    client = MultiProviderLLMClient(
        openrouter_key="invalid-key-test-1",
        gemini_key="invalid-key-test-2",
        huggingface_key="invalid-key-test-3",
        timeout_seconds=1.0
    )

    evidence = {
        "summary": {
            "liquid_cash": 120000.00,
            "total_overdue_receivables": 85000.00,
            "total_stranded_advances": 30000.00,
            "bounced_cheque_exposure": 15000.00,
            "upcoming_obligations_15d": 50000.00
        },
        "blockages": [
            {
                "customer_name": "Metro Retailers",
                "amount": 85000.00,
                "days_overdue": 24,
                "severity_score": 125800.0,
                "suggested_action": "Pause dispatch and issue formal reminder."
            }
        ],
        "contagion_paths": [
            {
                "causal_link": "Delayed receipt of ₹85,000 from Metro Retailers contributes directly to cash shortfall for GST due on 2026-10-25."
            }
        ]
    }

    result = client.generate(
        system_prompt="You are a financial advisor.",
        user_prompt="Where is my cash stuck?",
        evidence=evidence
    )

    assert result["provider"] == "deterministic_grounded_fallback"
    assert "₹120,000.00" in result["text"]
    assert "Metro Retailers" in result["text"]
    assert "₹85,000.00" in result["text"]
    assert len(result["fallback_reasons"]) > 0
