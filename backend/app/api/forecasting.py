"""
api/forecasting.py
==================
GET  /api/forecast/runway/{batch_id}    — 30-day cash projection
POST /api/forecast/simulate             — What-if stress scenario
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReconciliationBatch
from app.db.session import get_db
from app.schemas.forecast import RunwayOut, SimulationOut, SimulationRequest
from app.services import cash_forecaster, simulator as simulator_svc
from app.services.audit_logger import AuditLogger

router = APIRouter(prefix="/api/forecast", tags=["Forecasting"])


@router.get(
    "/runway/{batch_id}",
    response_model=RunwayOut,
    summary="Generate 30-day forward cash runway projection",
    description=(
        "Computes expected daily cash balance using verified settled inflows (C0), "
        "risk-adjusted pending receivables (P_collect: LOW=0.95, MEDIUM=0.70, HIGH=0.30), "
        "and outflows. Pure read-only — does not modify any records."
    ),
)
async def get_runway(
    batch_id: uuid.UUID,
    start_date: date = Query(default=None, description="Override projection start date (default: today)"),
    db: AsyncSession = Depends(get_db),
) -> RunwayOut:
    _start = start_date or date.today()

    # Validate batch
    await _require_batch(db, batch_id)

    result = await cash_forecaster.compute_runway(db, batch_id, _start)

    # Write audit log within same session (atomic with potential future writes)
    await AuditLogger.log_forecast(
        db=db,
        batch_id=batch_id,
        horizon_days=result.forecast_horizon_days,
        baseline_cash=result.baseline_cash,
        days_to_zero=result.liquidity_risk.days_to_zero,
    )

    return result


@router.post(
    "/simulate",
    response_model=SimulationOut,
    summary="Run what-if stress scenario over the 30-day forecast",
    description=(
        "Applies stress parameters (delay_days, default_rate, gateway_fee_surge) "
        "to the forecast pipeline and returns side-by-side baseline vs. simulated "
        "time-series. Pure in-memory — zero DB mutations."
    ),
)
async def simulate(
    body: SimulationRequest,
    db: AsyncSession = Depends(get_db),
) -> SimulationOut:
    await _require_batch(db, body.batch_id)

    result = await simulator_svc.run_simulation(db, body)

    # Audit the simulation run
    await AuditLogger.log_simulation(
        db=db,
        batch_id=body.batch_id,
        delay_days=body.delay_days,
        default_rate=body.default_rate,
        gateway_fee_surge=body.gateway_fee_surge,
        summary=result.summary,
    )

    return result


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
async def _require_batch(db: AsyncSession, batch_id: uuid.UUID) -> None:
    check = await db.execute(
        select(ReconciliationBatch.batch_id).where(
            ReconciliationBatch.batch_id == batch_id
        )
    )
    if check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found.",
        )
