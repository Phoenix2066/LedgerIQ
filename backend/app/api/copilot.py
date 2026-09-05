"""
api/copilot.py
==============
POST /api/copilot/chat — Conversational Finance AI Copilot endpoint.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReconciliationBatch
from app.db.session import get_db
from app.schemas.copilot import CopilotRequest, CopilotResponse
from app.services import copilot as copilot_service

router = APIRouter(prefix="/api/copilot", tags=["Copilot"])


@router.post(
    "/chat",
    response_model=CopilotResponse,
    summary="Ask the Finance AI Copilot a natural language question about a batch",
    description=(
        "Loads full batch context (metrics, exceptions, match data) and answers "
        "the user's finance operations query using kimi-k2.6:cloud. "
        "Falls back to structured keyword replies if KIMI_API_KEY is not configured."
    ),
)
async def copilot_chat(
    body: CopilotRequest,
    db: AsyncSession = Depends(get_db),
) -> CopilotResponse:
    # Validate batch exists
    batch_check = await db.execute(
        select(ReconciliationBatch.batch_id).where(
            ReconciliationBatch.batch_id == body.batch_id
        )
    )
    if batch_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch {body.batch_id} not found.",
        )

    user_message = (body.message or body.query or "").strip()
    if not user_message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty.",
        )

    return await copilot_service.chat(db, body.batch_id, user_message)
