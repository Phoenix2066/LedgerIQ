"""
services/copilot.py
====================
Conversational Finance AI Copilot service.

Loads full batch context (metrics + exceptions + match data) and answers
natural language queries using kimi-k2.6:cloud.

Falls back to a structured text summary if LLM is unavailable.
"""

import json
import logging
import uuid
from decimal import Decimal

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ExceptionItem, FinancialRecord, ReconciliationBatch
from app.schemas.copilot import CopilotResponse, CopilotSource

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt for Finance Copilot
# ---------------------------------------------------------------------------
_COPILOT_SYSTEM = """\
You are a senior Finance Controller AI Copilot embedded inside an AI Finance Controller system.
You have access to the complete reconciliation batch data provided below.

Your job is to answer the user's finance operations questions concisely and accurately.
- Cite specific transaction amounts, reference codes, and entity names where relevant.
- When you reference an exception, note its exception_id so it can be highlighted in the UI.
- Keep your reply to 3-5 sentences unless a longer structured answer is required.
- Respond in plain English (no markdown, no code blocks).

Batch Context:
{context}"""


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------
async def _build_batch_context(db: AsyncSession, batch_id: uuid.UUID) -> tuple[str, list[CopilotSource]]:
    """
    Fetches batch metrics + all exceptions and formats them into a compact
    context string for the LLM prompt. Also returns source objects for citation.
    """
    # Batch summary
    batch_result = await db.execute(
        select(ReconciliationBatch).where(ReconciliationBatch.batch_id == batch_id)
    )
    batch = batch_result.scalar_one_or_none()
    if batch is None:
        return f"Batch {batch_id} not found.", []

    # Risk distribution
    risk_result = await db.execute(
        select(ExceptionItem.risk_score, func.count())
        .where(ExceptionItem.batch_id == batch_id)
        .group_by(ExceptionItem.risk_score)
    )
    risk_counts = {r[0]: r[1] for r in risk_result.all()}

    # All exceptions with record details
    exc_result = await db.execute(
        select(ExceptionItem, FinancialRecord)
        .join(FinancialRecord, ExceptionItem.record_id == FinancialRecord.record_id)
        .where(ExceptionItem.batch_id == batch_id)
        .order_by(ExceptionItem.risk_score, FinancialRecord.amount.desc())
    )
    exceptions = exc_result.all()

    # High-risk exposure
    high_risk_total = sum(
        float(rec.amount)
        for exc, rec in exceptions
        if exc.risk_score == "HIGH" and float(rec.amount) > 0
    )
    fee_discrepancy_total = sum(
        float((rec.metadata_json or {}).get("gateway_fee", 0))
        for exc, rec in exceptions
        if rec.source_type == "GATEWAY"
    )

    # Format context
    lines = [
        f"=== BATCH SUMMARY ===",
        f"Batch ID: {batch_id}",
        f"Total Records: {batch.total_records}",
        f"Matched: {batch.matched_count} | Exceptions: {batch.exception_count} | Match Rate: {float(batch.match_rate):.1f}%",
        f"Risk Distribution — HIGH: {risk_counts.get('HIGH', 0)}, MEDIUM: {risk_counts.get('MEDIUM', 0)}, LOW: {risk_counts.get('LOW', 0)}",
        f"Total HIGH-risk exposure: ₹{high_risk_total:,.2f}",
        f"Total gateway fee discrepancy: ₹{fee_discrepancy_total:,.2f}",
        "",
        "=== EXCEPTION LIST ===",
    ]

    sources: list[CopilotSource] = [
        CopilotSource(
            type="batch_metric",
            id=str(batch_id),
            label=f"Batch {str(batch_id)[:8]}... | Match Rate {float(batch.match_rate):.1f}%",
        )
    ]

    for exc, rec in exceptions:
        meta = rec.metadata_json or {}
        entry = (
            f"[{exc.risk_score}] exception_id={exc.exception_id} "
            f"| source={rec.source_type} | entity='{rec.raw_entity_name}' "
            f"| amount=₹{float(rec.amount):,.2f} | ref={rec.reference_code or 'N/A'} "
            f"| date={rec.transaction_date} | anomaly={meta.get('anomaly_type', 'unknown')} "
            f"| diagnosis='{exc.ai_diagnosis or 'Pending diagnosis'}' "
            f"| action='{exc.recommended_action or 'N/A'}' | status={exc.status}"
        )
        lines.append(entry)
        sources.append(CopilotSource(
            type="exception",
            id=str(exc.exception_id),
            label=f"{exc.risk_score} | {rec.source_type} | ₹{float(rec.amount):,.2f} | {rec.raw_entity_name[:30]}",
            amount=float(rec.amount),
            risk_score=exc.risk_score,
        ))

    return "\n".join(lines), sources


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
async def _call_kimi_copilot(
    client: httpx.AsyncClient,
    system_prompt: str,
    user_message: str,
) -> str | None:
    if not settings.KIMI_API_KEY or settings.KIMI_API_KEY == "your-kimi-api-key-here":
        return None

    payload = {
        "model": settings.KIMI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }
    try:
        resp = await client.post(
            f"{settings.KIMI_BASE_URL}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.KIMI_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=settings.KIMI_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        return body["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning("Copilot LLM call failed: %s", e)
        return None


# ---------------------------------------------------------------------------
# Fallback: keyword-based structured reply
# ---------------------------------------------------------------------------
def _fallback_reply(message: str, context: str, sources: list[CopilotSource]) -> str:
    msg_lower = message.lower()
    exc_sources = [s for s in sources if s.type == "exception"]
    high_risk = [s for s in exc_sources if s.risk_score == "HIGH"]
    total_high_exposure = sum(s.amount or 0 for s in high_risk)

    if any(kw in msg_lower for kw in ["high risk", "high-risk", "high risk exception"]):
        names = [s.label for s in high_risk[:5]]
        return (
            f"There are {len(high_risk)} HIGH-risk exceptions in this batch "
            f"with total exposure of ₹{total_high_exposure:,.2f}. "
            f"Top items: {'; '.join(names)}."
        )
    if any(kw in msg_lower for kw in ["match rate", "matched", "reconciled"]):
        batch_src = next((s for s in sources if s.type == "batch_metric"), None)
        return (
            f"Batch metrics: {batch_src.label if batch_src else 'data unavailable'}. "
            f"There are {len(exc_sources)} total exceptions requiring review."
        )
    if any(kw in msg_lower for kw in ["summary", "summarize", "overview"]):
        return (
            f"This batch has {len(exc_sources)} exceptions. "
            f"HIGH-risk: {len(high_risk)} (₹{total_high_exposure:,.2f} exposure), "
            f"MEDIUM: {len([s for s in exc_sources if s.risk_score == 'MEDIUM'])}, "
            f"LOW: {len([s for s in exc_sources if s.risk_score == 'LOW'])}. "
            "Run POST /api/exceptions/diagnose/{batch_id} to get AI root-cause analysis."
        )
    return (
        "I have the full batch context loaded. "
        f"There are {len(exc_sources)} exceptions and {len(high_risk)} are HIGH-risk. "
        "Please configure KIMI_API_KEY in .env for full natural language Q&A capabilities."
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
async def chat(
    db: AsyncSession,
    batch_id: uuid.UUID,
    message: str,
) -> CopilotResponse:
    """Process a user message and return a copilot reply with source citations."""
    context, sources = await _build_batch_context(db, batch_id)
    system_prompt = _COPILOT_SYSTEM.format(context=context)

    async with httpx.AsyncClient() as client:
        reply = await _call_kimi_copilot(client, system_prompt, message)

    llm_used = reply is not None
    if reply is None:
        reply = _fallback_reply(message, context, sources)

    # Filter sources to those most relevant (limit to 10 for response size)
    relevant_sources = sources[:10]

    return CopilotResponse(reply=reply, sources=relevant_sources, llm_used=llm_used)
