"""
api/reconciliation.py
=====================
FastAPI router for Phase 2 reconciliation endpoints:

  POST /api/reconciliation/run/{batch_id}
      Triggers the 3-tier reconciliation cascade, risk triage, and DB update.

  GET  /api/reconciliation/summary/{batch_id}
      Returns batch match rate, counts, and risk breakdown.

  GET  /api/reconciliation/exceptions/{batch_id}
      Paginated exception list, optionally filtered by risk_score.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExceptionItem, FinancialRecord, RecordMatch, ReconciliationBatch
from app.db.session import get_db
from app.schemas.reconciliation import (
    ExceptionListOut,
    ExceptionOut,
    ReconciliationRunOut,
    ReconciliationSummaryOut,
    RiskBreakdown,
    TierBreakdown,
)
from app.services.audit_logger import AuditLogger
from app.services.reconciler import ReconciliationEngine, _Match
from app.services.risk_triage import triage_exceptions

router = APIRouter(prefix="/api/reconciliation", tags=["Reconciliation"])


# ---------------------------------------------------------------------------
# POST /api/reconciliation/run/{batch_id}
# ---------------------------------------------------------------------------
@router.post(
    "/run/{batch_id}",
    response_model=ReconciliationRunOut,
    status_code=status.HTTP_200_OK,
    summary="Trigger 3-tier reconciliation pipeline for a batch",
)
async def run_reconciliation(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReconciliationRunOut:
    """
    1. Validates the batch exists and has unmatched records.
    2. Runs ReconciliationEngine (Tier 1 → 2 → 3).
    3. Runs RiskTriageEngine on remaining unmatched records.
    4. Atomically persists all RecordMatch + ExceptionItem rows.
    5. Updates FinancialRecord statuses and ReconciliationBatch metrics.
    6. Returns reconciliation summary.
    """

    # ── Validate batch ────────────────────────────────────────────────────────
    batch_result = await db.execute(
        select(ReconciliationBatch).where(ReconciliationBatch.batch_id == batch_id)
    )
    batch = batch_result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found.",
        )

    # ── Guard: already reconciled? ───────────────────────────────────────────
    unmatched_count_result = await db.execute(
        select(func.count()).select_from(FinancialRecord).where(
            FinancialRecord.batch_id == batch_id,
            FinancialRecord.status == "UNMATCHED",
        )
    )
    unmatched_count = unmatched_count_result.scalar_one()

    if unmatched_count == 0:
        # Already reconciled — return current metrics
        risk_result = await db.execute(
            select(ExceptionItem.risk_score, func.count()).where(
                ExceptionItem.batch_id == batch_id
            ).group_by(ExceptionItem.risk_score)
        )
        risk_rows = {row[0]: row[1] for row in risk_result.all()}

        return ReconciliationRunOut(
            batch_id=batch_id,
            status="ALREADY_RECONCILED",
            total_records=batch.total_records,
            matched_count=batch.matched_count,
            exception_count=batch.exception_count,
            match_rate=float(batch.match_rate),
            tier1_exact=0,
            tier2_one_to_many=0,
            tier3_fuzzy=0,
            risk_breakdown=RiskBreakdown(
                high=risk_rows.get("HIGH", 0),
                medium=risk_rows.get("MEDIUM", 0),
                low=risk_rows.get("LOW", 0),
            ),
        )

    # ── Run reconciliation engine ────────────────────────────────────────────
    engine = ReconciliationEngine(db, batch_id)
    result = engine._fetch_unmatched  # for passing records to triage below
    recon_result = await engine.run()

    # ── Re-fetch all records to determine unmatched set ──────────────────────
    all_records_result = await db.execute(
        select(FinancialRecord).where(
            FinancialRecord.batch_id == batch_id,
            FinancialRecord.status == "UNMATCHED",  # still unmatched in DB
        )
    )
    # Filter to those not in matched_ids — these are true exceptions
    from app.services.reconciler import _Rec
    all_remaining_db = all_records_result.scalars().all()
    unmatched_for_triage = [
        _Rec(
            record_id=r.record_id,
            batch_id=r.batch_id,
            source_type=r.source_type,
            raw_entity_name=r.raw_entity_name,
            normalized_entity_name=r.normalized_entity_name,
            amount=float(r.amount),
            reference_code=r.reference_code,
            transaction_date=r.transaction_date,
            metadata_json=r.metadata_json or {},
        )
        for r in all_remaining_db
        if r.record_id not in recon_result.matched_ids
    ]

    # ── Risk triage ──────────────────────────────────────────────────────────
    exception_items = triage_exceptions(unmatched_for_triage, batch_id)

    # ── Atomic DB update ─────────────────────────────────────────────────────
    # 1. Bulk insert RecordMatch rows
    match_orm_rows = [
        RecordMatch(
            batch_id=batch_id,
            record_a_id=m.record_a_id,
            record_b_id=m.record_b_id,
            confidence_score=m.confidence_score,
            match_type=m.match_type,
            reasoning_trace=m.reasoning_trace,
        )
        for m in recon_result.matches
    ]
    if match_orm_rows:
        db.add_all(match_orm_rows)

    # 2. Bulk insert ExceptionItem rows
    if exception_items:
        db.add_all(exception_items)

    # 3. Log immutable audit trail events
    for m in recon_result.matches:
        await AuditLogger.log_auto_match(
            db=db,
            batch_id=batch_id,
            record_a_id=m.record_a_id,
            record_b_id=m.record_b_id,
            match_type=m.match_type,
            confidence_score=m.confidence_score,
            reasoning=m.reasoning_trace,
        )

    for ex in exception_items:
        await AuditLogger.log_exception_flagged(
            db=db,
            batch_id=batch_id,
            record_id=ex.record_id,
            risk_score=ex.risk_score,
            diagnosis=ex.ai_diagnosis or "Unmatched record flagged as exception.",
        )

    await db.flush()

    # 3. Update FinancialRecord status — MATCHED
    if recon_result.matched_ids:
        await db.execute(
            update(FinancialRecord)
            .where(FinancialRecord.record_id.in_(list(recon_result.matched_ids)))
            .values(status="MATCHED")
        )

    # 4. Update FinancialRecord status — EXCEPTION
    exception_record_ids = [ex.record_id for ex in exception_items]
    if exception_record_ids:
        await db.execute(
            update(FinancialRecord)
            .where(FinancialRecord.record_id.in_(exception_record_ids))
            .values(status="EXCEPTION")
        )

    # 5. Compute batch metrics
    matched_count = len(recon_result.matched_ids)
    exception_count = len(exception_items)
    total_records = batch.total_records
    match_rate = round((matched_count / total_records) * 100.0, 2) if total_records > 0 else 0.0

    # 6. Update ReconciliationBatch
    await db.execute(
        update(ReconciliationBatch)
        .where(ReconciliationBatch.batch_id == batch_id)
        .values(
            matched_count=matched_count,
            exception_count=exception_count,
            match_rate=match_rate,
        )
    )
    # Session auto-commits via get_db dependency

    # ── Risk breakdown ────────────────────────────────────────────────────────
    risk_counts: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for ex in exception_items:
        risk_counts[ex.risk_score] = risk_counts.get(ex.risk_score, 0) + 1

    return ReconciliationRunOut(
        batch_id=batch_id,
        status="COMPLETED",
        total_records=total_records,
        matched_count=matched_count,
        exception_count=exception_count,
        match_rate=match_rate,
        tier1_exact=recon_result.tier1_count,
        tier2_one_to_many=recon_result.tier2_count,
        tier3_fuzzy=recon_result.tier3_count,
        risk_breakdown=RiskBreakdown(
            high=risk_counts["HIGH"],
            medium=risk_counts["MEDIUM"],
            low=risk_counts["LOW"],
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/reconciliation/summary/{batch_id}
# ---------------------------------------------------------------------------
@router.get(
    "/summary/{batch_id}",
    response_model=ReconciliationSummaryOut,
    summary="Get reconciliation summary metrics for a batch",
)
async def get_summary(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ReconciliationSummaryOut:
    """Returns match rate %, counts, and risk distribution for a completed batch."""

    # Fetch batch
    batch_result = await db.execute(
        select(ReconciliationBatch).where(ReconciliationBatch.batch_id == batch_id)
    )
    batch = batch_result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found.",
        )

    # Risk distribution from exceptions table
    risk_result = await db.execute(
        select(ExceptionItem.risk_score, func.count())
        .where(ExceptionItem.batch_id == batch_id)
        .group_by(ExceptionItem.risk_score)
    )
    risk_rows = {row[0]: row[1] for row in risk_result.all()}

    # Tier cascade breakdown from record_matches
    tier_result = await db.execute(
        select(RecordMatch.match_type, func.count())
        .where(RecordMatch.batch_id == batch_id)
        .group_by(RecordMatch.match_type)
    )
    tier_rows = {row[0]: row[1] for row in tier_result.all()}

    # Resolved (human-in-the-loop) exceptions: anything no longer PENDING
    resolved_result = await db.execute(
        select(func.count()).select_from(ExceptionItem).where(
            ExceptionItem.batch_id == batch_id,
            ExceptionItem.status != "PENDING",
        )
    )
    resolved_count = resolved_result.scalar_one()

    unmatched = (
        batch.total_records - batch.matched_count - batch.exception_count
    )

    return ReconciliationSummaryOut(
        batch_id=batch_id,
        total_records=batch.total_records,
        matched_count=batch.matched_count,
        exception_count=batch.exception_count,
        unmatched_count=max(0, unmatched),
        match_rate=float(batch.match_rate),
        risk_breakdown=RiskBreakdown(
            high=risk_rows.get("HIGH", 0),
            medium=risk_rows.get("MEDIUM", 0),
            low=risk_rows.get("LOW", 0),
        ),
        resolved_count=resolved_count,
        tier_breakdown=TierBreakdown(
            tier1_exact=tier_rows.get("EXACT", 0),
            tier2_one_to_many=tier_rows.get("ONE_TO_MANY", 0),
            tier3_fuzzy=tier_rows.get("FUZZY", 0),
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/reconciliation/exceptions/{batch_id}
# ---------------------------------------------------------------------------
@router.get(
    "/exceptions/{batch_id}",
    response_model=ExceptionListOut,
    summary="List exceptions for a batch, optionally filtered by risk_score",
)
async def get_exceptions(
    batch_id: uuid.UUID,
    risk_score: Optional[str] = Query(
        default=None,
        description="Filter by risk level: HIGH, MEDIUM, or LOW",
        pattern="^(HIGH|MEDIUM|LOW)$",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> ExceptionListOut:
    """
    Returns paginated exception items joined with their FinancialRecord details.
    Optionally filter by `risk_score` (HIGH | MEDIUM | LOW).
    """
    # Validate batch exists
    batch_check = await db.execute(
        select(ReconciliationBatch.batch_id).where(
            ReconciliationBatch.batch_id == batch_id
        )
    )
    if batch_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found.",
        )

    # Build query — join ExceptionItem with FinancialRecord
    query = (
        select(ExceptionItem, FinancialRecord)
        .join(FinancialRecord, ExceptionItem.record_id == FinancialRecord.record_id)
        .where(ExceptionItem.batch_id == batch_id)
    )
    if risk_score:
        query = query.where(ExceptionItem.risk_score == risk_score.upper())

    # Total count (for pagination metadata)
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Paginated results ordered by risk priority
    risk_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    paged_query = query.offset(offset).limit(limit)
    rows_result = await db.execute(paged_query)
    rows = rows_result.all()

    # Sort by risk priority in Python (avoids CASE SQL expression complexity)
    rows_sorted = sorted(
        rows, key=lambda r: risk_order.get(r[0].risk_score, 3)
    )

    items = [
        ExceptionOut(
            exception_id=exc.exception_id,
            record_id=rec.record_id,
            source_type=rec.source_type,
            raw_entity_name=rec.raw_entity_name,
            normalized_entity_name=rec.normalized_entity_name,
            amount=float(rec.amount),
            reference_code=rec.reference_code,
            transaction_date=rec.transaction_date,
            risk_score=exc.risk_score,
            ai_diagnosis=exc.ai_diagnosis,
            recommended_action=exc.recommended_action,
            status=exc.status,
            entity_name=rec.normalized_entity_name or rec.raw_entity_name,
            drafted_journal_entry=getattr(exc, "drafted_journal_entry", None),
        )
        for exc, rec in rows_sorted
    ]

    return ExceptionListOut(
        batch_id=batch_id,
        total=total,
        risk_filter=risk_score,
        items=items,
    )
