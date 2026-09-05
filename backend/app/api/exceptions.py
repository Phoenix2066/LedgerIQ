"""
api/exceptions.py
=================
Human-in-the-loop exception management endpoints:

  POST /api/exceptions/{exception_id}/action
      Approve or reject an exception; optionally synthesize a DynamicRule.

  POST /api/exceptions/diagnose/{batch_id}
      Run the LLM diagnostic agent on all PENDING exceptions in a batch.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExceptionItem, FinancialRecord
from app.db.session import get_db
from app.schemas.diagnostic import (
    BatchDiagnosticOut,
    ExceptionActionOut,
    ExceptionActionRequest,
)
from app.services.audit_logger import AuditLogger
from app.services.diagnostic_agent import diagnose_batch_exceptions
from app.services.rule_synthesizer import synthesize_and_save

router = APIRouter(prefix="/api/exceptions", tags=["Exceptions"])


# ---------------------------------------------------------------------------
# POST /api/exceptions/{exception_id}/action
# ---------------------------------------------------------------------------
@router.post(
    "/{exception_id}/action",
    response_model=ExceptionActionOut,
    summary="Approve or reject an exception with optional rule synthesis",
    description=(
        "APPROVE: marks the exception as Approved, sets the linked FinancialRecord "
        "to RESOLVED, and optionally synthesizes an adaptive DynamicRule for future batches. "
        "REJECT: marks the exception as Rejected only."
    ),
)
async def exception_action(
    exception_id: uuid.UUID,
    body: ExceptionActionRequest,
    db: AsyncSession = Depends(get_db),
) -> ExceptionActionOut:
    # ── Fetch exception ──────────────────────────────────────────────────────
    exc_result = await db.execute(
        select(ExceptionItem, FinancialRecord)
        .join(FinancialRecord, ExceptionItem.record_id == FinancialRecord.record_id)
        .where(ExceptionItem.exception_id == exception_id)
    )
    row = exc_result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exception {exception_id} not found.",
        )
    exception, record = row

    if exception.status in ("APPROVED", "REJECTED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Exception already {exception.status}. Cannot re-process.",
        )

    rule_synthesized = False
    rule_name: str | None = None
    new_record_status = record.status   # default: unchanged

    # ── APPROVE path ─────────────────────────────────────────────────────────
    if body.action == "APPROVE":
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)

        # 1. Update ExceptionItem
        await db.execute(
            update(ExceptionItem)
            .where(ExceptionItem.exception_id == exception_id)
            .values(
                status="APPROVED",
                resolved_by=body.resolved_by,
                resolved_at=now,
            )
        )

        # 2. Update FinancialRecord → RESOLVED
        await db.execute(
            update(FinancialRecord)
            .where(FinancialRecord.record_id == record.record_id)
            .values(status="RESOLVED")
        )
        new_record_status = "RESOLVED"

        # 3. Synthesize rule if requested
        if body.synthesize_rule:
            rule = await synthesize_and_save(db, exception, record)
            if rule:
                rule_synthesized = True
                rule_name = rule.rule_name
                await AuditLogger.log_rule_synthesized(
                    db=db,
                    batch_id=exception.batch_id,
                    record_id=record.record_id,
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    rule_type=rule.rule_type,
                    pattern=rule.pattern,
                )

        await AuditLogger.log_human_action(
            db=db,
            batch_id=exception.batch_id,
            record_id=record.record_id,
            action="APPROVED",
            resolved_by=body.resolved_by,
        )

    # ── REJECT path ──────────────────────────────────────────────────────────
    else:
        from datetime import datetime, timezone
        now = datetime.now(tz=timezone.utc)
        await db.execute(
            update(ExceptionItem)
            .where(ExceptionItem.exception_id == exception_id)
            .values(
                status="REJECTED",
                resolved_by=body.resolved_by,
                resolved_at=now,
            )
        )

        await AuditLogger.log_human_action(
            db=db,
            batch_id=exception.batch_id,
            record_id=record.record_id,
            action="REJECTED",
            resolved_by=body.resolved_by,
        )

    # Session commits via get_db dependency
    return ExceptionActionOut(
        exception_id=exception_id,
        action_taken=body.action,
        new_status="APPROVED" if body.action == "APPROVE" else "REJECTED",
        record_status=new_record_status,
        rule_synthesized=rule_synthesized,
        rule_name=rule_name,
    )


# ---------------------------------------------------------------------------
# POST /api/exceptions/diagnose/{batch_id}
# ---------------------------------------------------------------------------
@router.post(
    "/diagnose/{batch_id}",
    response_model=BatchDiagnosticOut,
    summary="Run LLM diagnostic agent on all PENDING exceptions in a batch",
    description=(
        "Processes each PENDING ExceptionItem through the kimi-k2.6:cloud diagnostic agent. "
        "Updates ai_diagnosis, recommended_action, and drafted_journal_entry in the DB. "
        "Falls back to heuristic analysis if LLM is unavailable."
    ),
)
async def diagnose_exceptions(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BatchDiagnosticOut:
    # Quick existence check
    from app.db.models import ReconciliationBatch
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

    return await diagnose_batch_exceptions(db, batch_id)
