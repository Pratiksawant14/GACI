"""
Deterministic Cash-Flow Analysis Engine.
Calculates liquid balances, aging buckets, stranded advances, bounced cheques,
forward-looking cash deficit projections, and blockage severity rankings using arbitrary-precision Decimals.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from app.models.entities import Business, Customer, Supplier, BankAccount
from app.models.finance import SalesInvoice, Payment, SupplierAdvance, FinancialObligation
from app.schemas.analysis import (
    CashSummary,
    BlockageItem,
    AgingBucketSummary,
    DailyCashForecast,
    CashProjectionReport
)


class CashEngine:
    """Deterministic financial analytics and cash-blockage detection engine."""

    def __init__(self, session: Session):
        self.session = session

    def calculate_liquid_cash(self, business_id: uuid.UUID) -> Decimal:
        """Sums verified balances across all liquid bank accounts and cash tills."""
        stmt = select(func.coalesce(func.sum(BankAccount.current_balance), Decimal("0.00"))).where(
            BankAccount.business_id == business_id
        )
        total = self.session.scalar(stmt)
        return Decimal(str(total)) if total is not None else Decimal("0.00")

    def calculate_overdue_receivables(self, business_id: uuid.UUID, as_of: date) -> List[BlockageItem]:
        """Identifies unpaid invoices past due date and categorizes into aging buckets."""
        stmt = select(SalesInvoice).where(
            SalesInvoice.business_id == business_id,
            SalesInvoice.due_date < as_of,
            SalesInvoice.paid_amount < SalesInvoice.total_amount,
            SalesInvoice.status.notin_(["CANCELLED", "PAID"])
        ).order_by(SalesInvoice.due_date.asc())

        invoices = list(self.session.scalars(stmt).all())
        blockages: List[BlockageItem] = []

        for inv in invoices:
            days_overdue = (as_of - inv.due_date).days
            unpaid = inv.unpaid_balance
            # Severity formula: Amount * (1 + 0.02 * days)
            mult = Decimal("1.00") + (Decimal("0.02") * Decimal(days_overdue))
            severity = (unpaid * mult).quantize(Decimal("0.01"))

            cust_name = inv.customer.name if inv.customer else "Unknown Customer"

            blockages.append(BlockageItem(
                blockage_id=f"BLK-AR-{inv.invoice_number}",
                category="OVERDUE_RECEIVABLE",
                entity_name=cust_name,
                entity_type="Customer",
                source_record_id=str(inv.id),
                amount=unpaid,
                currency="INR",
                due_or_disbursed_date=inv.due_date,
                days_overdue=days_overdue,
                status=inv.status,
                severity_score=severity,
                evidence_summary=(
                    f"Invoice {inv.invoice_number} for total {inv.total_amount} was due on {inv.due_date}. "
                    f"Unpaid balance is {unpaid} ({days_overdue} days overdue)."
                ),
                suggested_action=f"Contact {cust_name} to demand immediate payment or renegotiate milestone settlement."
            ))

        return blockages

    def get_aging_buckets(self, blockages: List[BlockageItem]) -> List[AgingBucketSummary]:
        """Groups overdue receivable blockages into standard commercial aging buckets."""
        buckets = {
            "1-30 days": AgingBucketSummary(bucket="1-30 days"),
            "31-60 days": AgingBucketSummary(bucket="31-60 days"),
            "61-90 days": AgingBucketSummary(bucket="61-90 days"),
            "90+ days": AgingBucketSummary(bucket="90+ days")
        }

        for b in blockages:
            if b.category == "OVERDUE_RECEIVABLE":
                if b.days_overdue <= 30:
                    key = "1-30 days"
                elif b.days_overdue <= 60:
                    key = "31-60 days"
                elif b.days_overdue <= 90:
                    key = "61-90 days"
                else:
                    key = "90+ days"

                buckets[key].count += 1
                buckets[key].total_amount += b.amount

        return list(buckets.values())

    def calculate_stranded_advances(self, business_id: uuid.UUID, as_of: date) -> List[BlockageItem]:
        """Identifies supplier advances where goods have not been received past expected delivery date."""
        stmt = select(SupplierAdvance).where(
            SupplierAdvance.business_id == business_id,
            SupplierAdvance.expected_delivery_date < as_of,
            SupplierAdvance.fulfilled_amount < SupplierAdvance.advance_amount,
            SupplierAdvance.status.notin_(["FULFILLED", "REFUNDED"])
        ).order_by(SupplierAdvance.expected_delivery_date.asc())

        advances = list(self.session.scalars(stmt).all())
        blockages: List[BlockageItem] = []

        for adv in advances:
            days_overdue = (as_of - adv.expected_delivery_date).days
            unfulfilled = adv.unfulfilled_balance
            # Severity: unfulfilled * (1 + 0.03 * days)
            mult = Decimal("1.00") + (Decimal("0.03") * Decimal(days_overdue))
            severity = (unfulfilled * mult).quantize(Decimal("0.01"))

            sup_name = adv.supplier.name if adv.supplier else "Unknown Supplier"

            blockages.append(BlockageItem(
                blockage_id=f"BLK-ADV-{adv.advance_reference}",
                category="STRANDED_ADVANCE",
                entity_name=sup_name,
                entity_type="Supplier",
                source_record_id=str(adv.id),
                amount=unfulfilled,
                currency="INR",
                due_or_disbursed_date=adv.expected_delivery_date,
                days_overdue=days_overdue,
                status=adv.status,
                severity_score=severity,
                evidence_summary=(
                    f"Advance {adv.advance_reference} of {adv.advance_amount} was disbursed on {adv.disbursement_date}. "
                    f"Delivery was expected on {adv.expected_delivery_date}. "
                    f"Unfulfilled balance of {unfulfilled} is stranded without delivery for {days_overdue} days."
                ),
                suggested_action=f"Follow up with {sup_name} for immediate goods dispatch or initiate advance refund."
            ))

        return blockages

    def calculate_bounced_cheque_exposure(self, business_id: uuid.UUID, as_of: date) -> List[BlockageItem]:
        """Detects bounced cheques within the last 60 days that create phantom liquidity exposure."""
        cutoff_date = as_of - timedelta(days=60)
        stmt = select(Payment).where(
            Payment.business_id == business_id,
            Payment.status == "BOUNCED",
            Payment.payment_date >= cutoff_date
        )

        payments = list(self.session.scalars(stmt).all())
        blockages: List[BlockageItem] = []

        for pmt in payments:
            days_since = (as_of - pmt.payment_date).days
            severity = (pmt.amount * Decimal("1.50")).quantize(Decimal("0.01"))
            cust_name = pmt.customer.name if pmt.customer else "Counterparty"

            blockages.append(BlockageItem(
                blockage_id=f"BLK-CHQ-{pmt.payment_reference}",
                category="BOUNCED_CHEQUE",
                entity_name=cust_name,
                entity_type="Customer",
                source_record_id=str(pmt.id),
                amount=pmt.amount,
                currency="INR",
                due_or_disbursed_date=pmt.payment_date,
                days_overdue=days_since,
                status="BOUNCED",
                severity_score=severity,
                evidence_summary=(
                    f"Cheque instrument ref {pmt.payment_reference} for {pmt.amount} from {cust_name} "
                    f"bounced on {pmt.payment_date}. Provisional bank balance was reversed."
                ),
                suggested_action=f"Reissue debit note to {cust_name} and demand immediate electronic wire (NEFT/RTGS)."
            ))

        return blockages

    def get_all_blockages(self, business_id: uuid.UUID, as_of: date) -> List[BlockageItem]:
        """Aggregates all blockage categories and sorts by severity score descending."""
        ar_blockages = self.calculate_overdue_receivables(business_id, as_of)
        adv_blockages = self.calculate_stranded_advances(business_id, as_of)
        chq_blockages = self.calculate_bounced_cheque_exposure(business_id, as_of)

        all_items = ar_blockages + adv_blockages + chq_blockages
        all_items.sort(key=lambda x: x.severity_score, reverse=True)
        return all_items

    def project_cash_flow(self, business_id: uuid.UUID, as_of: date, window_days: int = 30) -> CashProjectionReport:
        """Projects daily cash balances comparing starting liquid cash with expected receipts and committed outflows."""
        liquid = self.calculate_liquid_cash(business_id)
        end_date = as_of + timedelta(days=window_days)

        # Expected inflows: Invoices due between as_of and end_date (not cancelled/paid)
        inv_stmt = select(SalesInvoice).where(
            SalesInvoice.business_id == business_id,
            SalesInvoice.due_date >= as_of,
            SalesInvoice.due_date <= end_date,
            SalesInvoice.status.notin_(["CANCELLED", "PAID"])
        )
        future_invoices = list(self.session.scalars(inv_stmt).all())
        inflows_by_date: Dict[date, Decimal] = {}
        for inv in future_invoices:
            inflows_by_date[inv.due_date] = inflows_by_date.get(inv.due_date, Decimal("0.00")) + inv.unpaid_balance

        # Committed outflows: Scheduled obligations between as_of and end_date
        ob_stmt = select(FinancialObligation).where(
            FinancialObligation.business_id == business_id,
            FinancialObligation.due_date >= as_of,
            FinancialObligation.due_date <= end_date,
            FinancialObligation.status == "SCHEDULED"
        )
        future_obligations = list(self.session.scalars(ob_stmt).all())
        outflows_by_date: Dict[date, Decimal] = {}
        for ob in future_obligations:
            outflows_by_date[ob.due_date] = outflows_by_date.get(ob.due_date, Decimal("0.00")) + ob.amount

        daily_forecasts: List[DailyCashForecast] = []
        current_balance = liquid
        first_deficit_date: Optional[date] = None
        max_deficit = Decimal("0.00")
        total_inflows = Decimal("0.00")
        total_outflows = Decimal("0.00")

        for day_offset in range(window_days + 1):
            curr_date = as_of + timedelta(days=day_offset)
            opening = current_balance
            inflow = inflows_by_date.get(curr_date, Decimal("0.00"))
            outflow = outflows_by_date.get(curr_date, Decimal("0.00"))
            closing = opening + inflow - outflow

            total_inflows += inflow
            total_outflows += outflow

            has_deficit = closing < Decimal("0.00")
            if has_deficit:
                if first_deficit_date is None:
                    first_deficit_date = curr_date
                deficit_amount = abs(closing)
                if deficit_amount > max_deficit:
                    max_deficit = deficit_amount

            daily_forecasts.append(DailyCashForecast(
                forecast_date=curr_date,
                day_offset=day_offset,
                opening_balance=opening,
                expected_inflows=inflow,
                committed_outflows=outflow,
                closing_balance=closing,
                has_deficit=has_deficit
            ))
            current_balance = closing

        return CashProjectionReport(
            as_of_date=as_of,
            starting_liquid_cash=liquid,
            forecast_horizon_days=window_days,
            daily_forecasts=daily_forecasts,
            first_deficit_date=first_deficit_date,
            max_deficit_amount=max_deficit,
            total_expected_inflows=total_inflows,
            total_committed_outflows=total_outflows
        )

    def get_cash_summary(self, business_id: uuid.UUID, as_of: date) -> CashSummary:
        """Returns consolidated financial status summary."""
        liquid = self.calculate_liquid_cash(business_id)
        blockages = self.get_all_blockages(business_id, as_of)

        total_ar = sum((b.amount for b in blockages if b.category == "OVERDUE_RECEIVABLE"), Decimal("0.00"))
        total_adv = sum((b.amount for b in blockages if b.category == "STRANDED_ADVANCE"), Decimal("0.00"))
        total_chq = sum((b.amount for b in blockages if b.category == "BOUNCED_CHEQUE"), Decimal("0.00"))

        proj_15 = self.project_cash_flow(business_id, as_of, window_days=15)
        proj_30 = self.project_cash_flow(business_id, as_of, window_days=30)

        # Final projected closing positions
        closing_15 = proj_15.daily_forecasts[-1].closing_balance if proj_15.daily_forecasts else liquid
        closing_30 = proj_30.daily_forecasts[-1].closing_balance if proj_30.daily_forecasts else liquid

        return CashSummary(
            as_of_date=as_of,
            liquid_cash=liquid,
            total_overdue_receivables=total_ar,
            total_stranded_advances=total_adv,
            bounced_cheque_exposure=total_chq,
            upcoming_obligations_15d=proj_15.total_committed_outflows,
            upcoming_obligations_30d=proj_30.total_committed_outflows,
            projected_net_position_15d=closing_15,
            projected_net_position_30d=closing_30
        )
