"""
api/audit.py
============
GET /api/audit/trail/{batch_id}    — Full chronological audit trail for a batch
GET /api/audit/export/{batch_id}   — Export complete audit trail as JSON or CSV
"""

import csv
import io
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, ReconciliationBatch
from app.db.session import get_db
from app.schemas.audit import AuditExportOut, AuditLogOut, AuditTrailOut

router = APIRouter(prefix="/api/audit", tags=["Audit"])


# ---------------------------------------------------------------------------
# GET /api/audit/trail/{batch_id}
# ---------------------------------------------------------------------------
@router.get(
    "/trail/{batch_id}",
    response_model=AuditTrailOut,
    summary="Get full chronological audit trail for a batch",
    description=(
        "Returns every immutable audit event logged for this batch in chronological order. "
        "Filter by action_type to narrow results (e.g., AUTO_MATCH, EXCEPTION_FLAGGED)."
    ),
)
async def get_audit_trail(
    batch_id: uuid.UUID,
    action_type: Optional[str] = Query(
        default=None,
        description="Filter by action type (e.g. AUTO_MATCH, HUMAN_APPROVED)",
    ),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> AuditTrailOut:
    await _require_batch(db, batch_id)

    query = (
        select(AuditLog)
        .where(AuditLog.batch_id == batch_id)
        .order_by(asc(AuditLog.created_at))
    )
    if action_type:
        query = query.where(AuditLog.action_type == action_type.upper())

    # Total count
    from sqlalchemy import func
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    paged = await db.execute(query.offset(offset).limit(limit))
    rows = paged.scalars().all()

    return AuditTrailOut(
        batch_id=batch_id,
        total_events=total,
        events=[
            AuditLogOut(
                audit_id=r.audit_id,
                batch_id=r.batch_id,
                record_id=r.record_id,
                action_type=r.action_type,
                actor=r.actor,
                confidence_score=float(r.confidence_score) if r.confidence_score is not None else None,
                reasoning_snapshot=r.reasoning_snapshot,
                changes_payload=r.changes_payload,
                created_at=r.created_at,
            )
            for r in rows
        ],
    )


# ---------------------------------------------------------------------------
# GET /api/audit/export/{batch_id}
# ---------------------------------------------------------------------------
@router.get(
    "/export/{batch_id}",
    response_model=AuditExportOut,
    summary="Export complete immutable audit trail as JSON or CSV",
    description=(
        "Generates a full structured export of the audit trail. "
        "Use ?format=csv for a spreadsheet-compatible output. "
        "Use ?format=json (default) for machine-readable export."
    ),
)
async def export_audit_trail(
    batch_id: uuid.UUID,
    format: str = Query(default="json", pattern="^(json|csv)$", description="Export format: json or csv"),
    db: AsyncSession = Depends(get_db),
) -> AuditExportOut:
    await _require_batch(db, batch_id)

    # Fetch all events in chronological order (no pagination for export)
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.batch_id == batch_id)
        .order_by(asc(AuditLog.created_at))
    )
    rows = result.scalars().all()

    if format == "csv":
        payload = _to_csv(rows)
    else:
        payload = _to_json(rows, batch_id)

    return AuditExportOut(
        batch_id=batch_id,
        format=format,
        total_events=len(rows),
        exported_at=datetime.now(tz=timezone.utc),
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def _to_json(rows: list[AuditLog], batch_id: uuid.UUID) -> str:
    data = {
        "batch_id": str(batch_id),
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_events": len(rows),
        "events": [
            {
                "audit_id": str(r.audit_id),
                "batch_id": str(r.batch_id),
                "record_id": str(r.record_id) if r.record_id else None,
                "action_type": r.action_type,
                "actor": r.actor,
                "confidence_score": (
                    float(r.confidence_score) if r.confidence_score is not None else None
                ),
                "reasoning_snapshot": r.reasoning_snapshot,
                "changes_payload": r.changes_payload,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }
    return json.dumps(data, indent=2, default=str)


def _to_csv(rows: list[AuditLog]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "audit_id", "batch_id", "record_id", "action_type", "actor",
        "confidence_score", "reasoning_snapshot", "changes_payload", "created_at",
    ])
    for r in rows:
        writer.writerow([
            str(r.audit_id),
            str(r.batch_id),
            str(r.record_id) if r.record_id else "",
            r.action_type,
            r.actor,
            float(r.confidence_score) if r.confidence_score is not None else "",
            r.reasoning_snapshot or "",
            json.dumps(r.changes_payload) if r.changes_payload else "",
            r.created_at.isoformat() if r.created_at else "",
        ])
    return output.getvalue()


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
