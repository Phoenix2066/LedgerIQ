"""
services/cash_forecaster.py
============================
30-day forward cash runway projection engine.

Formula:
  C(t) = C0
       + Σ settled_inflows(t)           # reconciled BANK/GATEWAY records up to t
       + Σ pending_receivables(t) × P_collect  # risk-weighted unmatched invoices
       - Σ outflows(t)                  # BANK debit records (negative amounts)

Risk-adjusted collection probability:
  LOW    → P_collect = 0.95
  MEDIUM → P_collect = 0.70
  HIGH   → P_collect = 0.30

All arithmetic uses Python float with 2dp rounding per Execution Requirement #3.
DB records are read-only — no mutations (Execution Requirement #2).
"""

import logging
from datetime import date, timedelta
from typing import Optional

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExceptionItem, FinancialRecord, RecordMatch, ReconciliationBatch
from app.schemas.forecast import ForecastDataPoint, LiquidityRiskMetric, RunwayOut

logger = logging.getLogger(__name__)

FORECAST_DAYS = 30

# Risk-adjusted collection probabilities
P_COLLECT = {"LOW": 0.95, "MEDIUM": 0.70, "HIGH": 0.30}
P_COLLECT_DEFAULT = 0.50   # for UNMATCHED records with no exception entry

# ---------------------------------------------------------------------------
# Internal data holder (pure read, no ORM session touch after load)
# ---------------------------------------------------------------------------

class _RecordSnapshot:
    """Immutable snapshot of a FinancialRecord row for in-memory compute."""
    __slots__ = ("record_id", "source_type", "amount", "transaction_date",
                 "status", "risk_score")

    def __init__(self, record: FinancialRecord, risk_score: Optional[str] = None):
        self.record_id = record.record_id
        self.source_type = record.source_type
        self.amount = float(record.amount)
        self.transaction_date = record.transaction_date
        self.status = record.status
        self.risk_score = risk_score  # from ExceptionItem if exists


# ---------------------------------------------------------------------------
# Core projection engine (pure function — no DB writes)
# ---------------------------------------------------------------------------

def _project(
    snapshots: list[_RecordSnapshot],
    start_date: date,
    delay_days: int = 0,
    default_rate: float = 0.0,
    gateway_fee_surge: float = 0.0,
) -> list[ForecastDataPoint]:
    """
    Pure in-memory 30-day projection. Returns list of ForecastDataPoint.
    Parameters:
        delay_days       — shifts pending collection dates forward by N days
        default_rate     — multiplies pending receivable values by (1 - default_rate)
        gateway_fee_surge — additional fee fraction deducted from gateway settlements
    """

    # Split records by category
    # C0 source: MATCHED BANK deposits (verified cash in)
    c0_records = [s for s in snapshots if s.status == "MATCHED" and s.source_type == "BANK" and s.amount > 0]
    c0 = round(sum(s.amount for s in c0_records), 2)

    # Settled inflows: MATCHED INVOICE and GATEWAY credits
    settled = [s for s in snapshots if s.status == "MATCHED"
               and s.source_type in ("INVOICE", "GATEWAY") and s.amount > 0]

    # Gateway fee surge adjustment on settled gateway records
    def settled_amount(s: _RecordSnapshot) -> float:
        if s.source_type == "GATEWAY":
            return round(s.amount * (1.0 - gateway_fee_surge), 2)
        return s.amount

    # Outflows: BANK debits (amounts already negative in synthetic data)
    outflows = [s for s in snapshots if s.source_type == "BANK" and s.amount < 0]

    # Pending receivables: EXCEPTION or UNMATCHED invoices
    pending = [s for s in snapshots if s.source_type == "INVOICE"
               and s.status in ("EXCEPTION", "UNMATCHED")]

    def pending_amount(s: _RecordSnapshot) -> float:
        p = P_COLLECT.get(s.risk_score or "", P_COLLECT_DEFAULT)
        return round(s.amount * p * (1.0 - default_rate), 2)

    def pending_collection_date(s: _RecordSnapshot) -> date:
        return s.transaction_date + timedelta(days=delay_days)

    # Build day-by-day projection
    points: list[ForecastDataPoint] = []
    running_balance = c0

    for day_offset in range(FORECAST_DAYS):
        day = start_date + timedelta(days=day_offset)

        # Settled inflows on this day (or before — cumulative from start)
        day_settled = sum(
            settled_amount(s) for s in settled
            if s.transaction_date <= day
        )

        # Pending receivables expected by this day (with delay)
        day_pending = sum(
            pending_amount(s) for s in pending
            if pending_collection_date(s) <= day
        )

        # Outflows up to this day
        day_outflows = sum(abs(s.amount) for s in outflows if s.transaction_date <= day)

        projected = round(c0 + day_settled + day_pending - day_outflows, 2)
        at_risk = round(day_pending, 2)
        settled_total = round(day_settled, 2)

        points.append(ForecastDataPoint(
            date=day,
            projected_balance=projected,
            settled_cash=settled_total,
            at_risk_cash=at_risk,
        ))

    return points


def _compute_liquidity_metrics(
    projection: list[ForecastDataPoint],
    snapshots: list[_RecordSnapshot],
) -> LiquidityRiskMetric:
    """Derive liquidity risk summary from projection series."""
    balances = [p.projected_balance for p in projection]

    min_balance = min(balances) if balances else 0.0
    min_idx = balances.index(min_balance) if balances else 0
    min_date = projection[min_idx].date if projection else None

    # Days to zero: first day where balance ≤ 0
    days_to_zero: Optional[int] = None
    for i, p in enumerate(projection):
        if p.projected_balance <= 0:
            days_to_zero = i
            break

    # Risk exposure by tier
    high_risk = sum(s.amount for s in snapshots
                    if s.risk_score == "HIGH" and s.source_type == "INVOICE")
    medium_risk = sum(s.amount for s in snapshots
                      if s.risk_score == "MEDIUM" and s.source_type == "INVOICE")
    low_risk = sum(s.amount for s in snapshots
                   if s.risk_score == "LOW" and s.source_type == "INVOICE")
    total_at_risk = round(high_risk + medium_risk + low_risk, 2)
    total_settled = round(sum(p.settled_cash for p in projection[-1:]), 2)

    return LiquidityRiskMetric(
        days_to_zero=days_to_zero,
        minimum_balance=round(min_balance, 2),
        minimum_balance_date=min_date,
        total_at_risk=total_at_risk,
        total_settled=total_settled,
        high_risk_exposure=round(high_risk, 2),
        medium_risk_exposure=round(medium_risk, 2),
        low_risk_exposure=round(low_risk, 2),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def compute_runway(
    db: AsyncSession,
    batch_id: uuid.UUID,
    start_date: Optional[date] = None,
) -> RunwayOut:
    """
    Compute the baseline 30-day cash runway for a batch.
    Pure read — does NOT write any DB rows.
    """
    if start_date is None:
        start_date = date.today()

    # Load all records (read-only)
    records_result = await db.execute(
        select(FinancialRecord).where(FinancialRecord.batch_id == batch_id)
    )
    records = records_result.scalars().all()

    # Load exception risk scores for EXCEPTION records
    exc_result = await db.execute(
        select(ExceptionItem.record_id, ExceptionItem.risk_score)
        .where(ExceptionItem.batch_id == batch_id)
    )
    risk_map: dict[uuid.UUID, str] = {row[0]: row[1] for row in exc_result.all()}

    snapshots = [_RecordSnapshot(r, risk_map.get(r.record_id)) for r in records]

    # Compute C0
    c0 = round(sum(
        s.amount for s in snapshots
        if s.status == "MATCHED" and s.source_type == "BANK" and s.amount > 0
    ), 2)

    projection = _project(snapshots, start_date)
    liquidity = _compute_liquidity_metrics(projection, snapshots)

    return RunwayOut(
        batch_id=batch_id,
        baseline_cash=c0,
        forecast_horizon_days=FORECAST_DAYS,
        projection=projection,
        liquidity_risk=liquidity,
    )
