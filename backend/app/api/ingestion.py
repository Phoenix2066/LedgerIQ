"""
ingestion.py
============
FastAPI router for Phase 1 batch ingestion endpoints:

  POST /api/batch/generate-synthetic
      Generates synthetic records, normalizes entity names via local Ollama
      (with regex fallback), persists to Neon Postgres, returns batch summary.

  GET  /api/batch/{batch_id}/records
      Returns all FinancialRecords for the given batch.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinancialRecord, ReconciliationBatch
from app.db.session import get_db
from app.schemas.batch import BatchRecordsOut, BatchSummaryOut, FinancialRecordOut
from app.services.normalizer import normalize_batch
from app.services.synthetic_generator import generate_synthetic_batch, get_batch_stats

router = APIRouter(prefix="/api/batch", tags=["Ingestion"])


# ---------------------------------------------------------------------------
# POST /api/batch/generate-synthetic
# ---------------------------------------------------------------------------
@router.post(
    "/generate-synthetic",
    response_model=BatchSummaryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate & ingest a synthetic 55-record multi-source batch",
)
async def generate_synthetic(db: AsyncSession = Depends(get_db)) -> BatchSummaryOut:
    """
    1. Generate 55 synthetic financial records (BANK / GATEWAY / INVOICE).
    2. Run entity names through the Ollama normalizer (regex fallback if offline).
    3. Persist a ReconciliationBatch + all FinancialRecords to Neon Postgres.
    4. Return batch summary JSON.
    """
    batch_id = uuid.uuid4()
    now = datetime.now(tz=timezone.utc)

    # ── Step 1: Generate raw records ────────────────────────────────────────
    raw_records = generate_synthetic_batch(batch_id)
    stats = get_batch_stats(raw_records)

    # ── Step 2: Normalize entity names concurrently ──────────────────────────
    raw_names = [r["raw_entity_name"] for r in raw_records]
    normalized_names = await normalize_batch(raw_names)
    for rec, norm_name in zip(raw_records, normalized_names):
        rec["normalized_entity_name"] = norm_name

    # ── Step 3: Persist batch header ─────────────────────────────────────────
    batch = ReconciliationBatch(
        batch_id=batch_id,
        total_records=stats["total"],
        matched_count=0,       # updated by Phase 2 reconciliation engine
        exception_count=0,
        match_rate=0.0,
        created_at=now,
    )
    db.add(batch)
    await db.flush()  # get batch_id into DB without committing yet

    # ── Step 4: Persist financial records ────────────────────────────────────
    orm_records = [FinancialRecord(**rec) for rec in raw_records]
    db.add_all(orm_records)
    # Session commits automatically via get_db dependency on successful return

    return BatchSummaryOut(
        batch_id=batch_id,
        total_records=stats["total"],
        bank_count=stats["bank"],
        gateway_count=stats["gateway"],
        invoice_count=stats["invoice"],
        created_at=now,
    )


# ---------------------------------------------------------------------------
# GET /api/batch/{batch_id}/records
# ---------------------------------------------------------------------------
@router.get(
    "/{batch_id}/records",
    response_model=BatchRecordsOut,
    summary="Fetch all FinancialRecords for a given batch",
)
async def get_batch_records(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> BatchRecordsOut:
    """
    Returns all ingested FinancialRecords for the specified batch_id.
    Raises 404 if the batch does not exist.
    """
    # Verify batch exists
    batch_result = await db.execute(
        select(ReconciliationBatch).where(
            ReconciliationBatch.batch_id == batch_id
        )
    )
    batch = batch_result.scalar_one_or_none()
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {batch_id} not found.",
        )

    # Fetch records
    records_result = await db.execute(
        select(FinancialRecord)
        .where(FinancialRecord.batch_id == batch_id)
        .order_by(FinancialRecord.transaction_date, FinancialRecord.source_type)
    )
    records = records_result.scalars().all()

    return BatchRecordsOut(
        batch_id=batch_id,
        total_records=len(records),
        records=[FinancialRecordOut.model_validate(r) for r in records],
    )
