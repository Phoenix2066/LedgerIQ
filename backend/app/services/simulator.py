"""
services/simulator.py
======================
What-if scenario stress-testing engine.

Applies three independent stressors over the cash_forecaster projection:
  delay_days       — shifts pending receivable collection dates forward
  default_rate     — haircuts pending receivable values by (1 - rate)
  gateway_fee_surge — deducts additional fee from gateway settlements

Pure in-memory compute — ZERO DB mutations (Execution Requirement #2).
"""

import logging
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExceptionItem, FinancialRecord
from app.schemas.forecast import ForecastDataPoint, RunwayDelta, SimulationOut, SimulationRequest
from app.services.cash_forecaster import (
    FORECAST_DAYS,
    _RecordSnapshot,
    _compute_liquidity_metrics,
    _project,
)

logger = logging.getLogger(__name__)


async def run_simulation(
    db: AsyncSession,
    request: SimulationRequest,
    start_date: Optional[date] = None,
) -> SimulationOut:
    """
    Returns baseline vs. stressed 30-day projections side-by-side.
    Pure in-memory — does NOT write any DB rows.
    """
    if start_date is None:
        start_date = date.today()

    # ── Load records (read-only) ─────────────────────────────────────────────
    records_result = await db.execute(
        select(FinancialRecord).where(FinancialRecord.batch_id == request.batch_id)
    )
    records = records_result.scalars().all()

    exc_result = await db.execute(
        select(ExceptionItem.record_id, ExceptionItem.risk_score)
        .where(ExceptionItem.batch_id == request.batch_id)
    )
    risk_map: dict[uuid.UUID, str] = {row[0]: row[1] for row in exc_result.all()}
    snapshots = [_RecordSnapshot(r, risk_map.get(r.record_id)) for r in records]

    # ── Baseline projection ──────────────────────────────────────────────────
    baseline = _project(snapshots, start_date)

    # ── Stressed projection ──────────────────────────────────────────────────
    simulated = _project(
        snapshots,
        start_date,
        delay_days=request.delay_days,
        default_rate=request.default_rate,
        gateway_fee_surge=request.gateway_fee_surge,
    )

    # ── Compute deltas ───────────────────────────────────────────────────────
    deltas: list[RunwayDelta] = []
    for i, (base, sim) in enumerate(zip(baseline, simulated)):
        delta = round(sim.projected_balance - base.projected_balance, 2)
        delta_pct = (
            round((delta / abs(base.projected_balance)) * 100, 2)
            if base.projected_balance != 0
            else 0.0
        )
        deltas.append(RunwayDelta(
            day_index=i,
            date=base.date,
            baseline_balance=base.projected_balance,
            simulated_balance=sim.projected_balance,
            delta=delta,
            delta_pct=delta_pct,
        ))

    # ── Summary narrative ────────────────────────────────────────────────────
    if deltas:
        worst = min(deltas, key=lambda d: d.delta)
        max_neg_day = worst.day_index
        max_neg_amount = abs(worst.delta)

        parts = []
        if request.delay_days > 0:
            parts.append(f"{request.delay_days}-day collection delay")
        if request.default_rate > 0:
            parts.append(f"{request.default_rate:.0%} default rate")
        if request.gateway_fee_surge > 0:
            parts.append(f"{request.gateway_fee_surge:.1%} fee surge")

        scenario_desc = " + ".join(parts) if parts else "no stress"
        if worst.delta < 0:
            summary = (
                f"Under {scenario_desc}, cash position reduces by ₹{max_neg_amount:,.2f} "
                f"at Day {max_neg_day + 1} (worst impact on {worst.date})."
            )
        else:
            summary = (
                f"Under {scenario_desc}, simulation shows no significant negative "
                f"impact. Maximum reduction: ₹{max_neg_amount:,.2f}."
            )
        max_negative_impact_day = max_neg_day if worst.delta < 0 else None
        max_negative_impact_amount = max_neg_amount
    else:
        summary = "No records available for simulation."
        max_negative_impact_day = None
        max_negative_impact_amount = 0.0

    return SimulationOut(
        batch_id=request.batch_id,
        parameters=request,
        baseline=baseline,
        simulated=simulated,
        deltas=deltas,
        summary=summary,
        max_negative_impact_day=max_negative_impact_day,
        max_negative_impact_amount=round(max_negative_impact_amount, 2),
    )
