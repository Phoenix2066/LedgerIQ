"""
diagnostic_agent.py
====================
LLM-powered root-cause diagnostic agent for financial exceptions.

Workflow per exception:
  1. Fetch ExceptionItem + FinancialRecord from DB
  2. Build structured prompt with transaction context
  3. Call kimi-k2.6:cloud (OpenAI-compatible API via httpx)
  4. Parse + validate JSON response with Pydantic (strict fallback on failure)
  5. Persist ai_diagnosis, recommended_action, drafted_journal_entry to DB

Falls back gracefully to heuristic diagnosis if:
  - KIMI_API_KEY is not set
  - Network call times out
  - LLM returns malformed JSON
"""

import json
import logging
import uuid
from datetime import date

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ExceptionItem, FinancialRecord, ReconciliationBatch
from app.schemas.diagnostic import (
    BatchDiagnosticOut,
    DiagnosticLLMResponse,
    DiagnosticOut,
    JournalEntrySchema,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt (exact spec from prompt.md)
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are an expert Corporate Financial Controller AI.
Analyze the unmatched transaction and return a strict JSON response containing:
1. "diagnosis": High-precision 1-2 sentence explanation of why this transaction failed to reconcile.
2. "recommended_action": Concrete remediation action (e.g., "Write-off Fee Discrepancy", "Allocate to Suspense Clearing", "Request Vendor Invoice").
3. "drafted_journal_entry": {
     "debit_account": string,
     "credit_account": string,
     "amount": float,
     "memo": string
   }
Return ONLY valid JSON. No markdown, no extra text."""

# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------
_HEURISTIC_ACCOUNTS = {
    "BANK": ("Bank / Cash", "Suspense Clearing Account"),
    "GATEWAY": ("Gateway Settlement Receivable", "Fee Expense Account"),
    "INVOICE": ("Accounts Receivable", "Revenue / Income Account"),
}


def _heuristic_diagnosis(record: FinancialRecord, exception: ExceptionItem) -> DiagnosticLLMResponse:
    """Rule-based fallback when LLM is unavailable."""
    meta = record.metadata_json or {}
    anomaly = meta.get("anomaly_type", "unknown")
    risk = exception.risk_score
    amount = float(record.amount)
    debit, credit = _HEURISTIC_ACCOUNTS.get(record.source_type, ("Suspense", "Suspense"))

    diagnosis_map = {
        "missing_reference": "Transaction lacks a reference code, preventing automated matching against invoices or settlements.",
        "duplicate_reference": "Reference code matches an already-reconciled record, indicating a potential duplicate entry.",
        "fee_discrepancy_gt_2pct": "Gateway fee deducted exceeds the expected 2% processing rate, creating an amount mismatch.",
        "stale_settlement_over_7d": "Settlement record is older than 7 days, suggesting a delayed or missed bank posting.",
        "chargeback_high_value": "High-value chargeback posted without a corresponding dispute credit note.",
        "partial_refund": "Partial refund amount does not match any outstanding invoice balance.",
        "orphan_invoice_no_payment": "Invoice has no corresponding bank or gateway payment recorded in this batch.",
    }
    diagnosis = diagnosis_map.get(
        anomaly,
        f"{risk}-risk unmatched {record.source_type} record of ₹{amount:,.2f} could not be paired with any counterpart record.",
    )
    action_map = {
        "missing_reference": "Obtain reference code from vendor/bank and re-run reconciliation.",
        "duplicate_reference": "Verify with bank and void duplicate entry if confirmed.",
        "fee_discrepancy_gt_2pct": "Write-off Fee Discrepancy — raise dispute with payment gateway.",
        "stale_settlement_over_7d": "Allocate to Suspense Clearing and follow up with bank for late posting.",
        "chargeback_high_value": "Escalate to finance controller; initiate chargeback dispute process.",
        "partial_refund": "Match against open credit notes or request revised invoice.",
        "orphan_invoice_no_payment": "Request Vendor Invoice — contact vendor for payment confirmation.",
    }
    action = action_map.get(anomaly, "Escalate to senior controller for manual verification.")

    return DiagnosticLLMResponse(
        diagnosis=diagnosis,
        recommended_action=action,
        drafted_journal_entry=JournalEntrySchema(
            debit_account=debit,
            credit_account=credit,
            amount=amount,
            memo=f"Unreconciled {record.source_type} — {anomaly or 'no match found'} [{record.raw_entity_name}]",
        ),
    )


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------
async def _call_kimi(
    client: httpx.AsyncClient,
    user_content: str,
) -> DiagnosticLLMResponse | None:
    """
    Call kimi-k2.6 via OpenAI-compatible chat completions endpoint.
    Returns None if call fails or response is unparseable.
    """
    if not settings.KIMI_API_KEY or settings.KIMI_API_KEY == "your-kimi-api-key-here":
        return None

    payload = {
        "model": settings.KIMI_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
        "max_tokens": 512,
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
        raw_content = body["choices"][0]["message"]["content"]
        parsed = json.loads(raw_content)
        return DiagnosticLLMResponse.model_validate(parsed)
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        logger.warning("Kimi LLM timeout/connection error: %s", e)
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.warning("Kimi response parse error: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected kimi error: %s", e)
        return None


# ---------------------------------------------------------------------------
# Public: diagnose a single exception
# ---------------------------------------------------------------------------
async def diagnose_exception(
    db: AsyncSession,
    exception_id: uuid.UUID,
) -> DiagnosticOut | None:
    """
    Diagnose a single ExceptionItem. Returns DiagnosticOut or None if not found.
    """
    # Fetch exception + record
    exc_result = await db.execute(
        select(ExceptionItem, FinancialRecord)
        .join(FinancialRecord, ExceptionItem.record_id == FinancialRecord.record_id)
        .where(ExceptionItem.exception_id == exception_id)
    )
    row = exc_result.first()
    if row is None:
        return None

    exception, record = row

    # Build LLM user content
    meta = record.metadata_json or {}
    user_content = f"""Transaction Details:
- Source: {record.source_type}
- Entity: {record.raw_entity_name} (normalized: {record.normalized_entity_name or 'N/A'})
- Amount: ₹{float(record.amount):,.2f}
- Reference: {record.reference_code or 'MISSING'}
- Date: {record.transaction_date}
- Risk Score: {exception.risk_score}
- Anomaly Type: {meta.get('anomaly_type', 'unknown')}
- Batch metadata: {meta}

Existing triage diagnosis: {exception.ai_diagnosis or 'None'}

Why did this transaction fail to reconcile? Provide root cause and remediation."""

    # Try LLM first
    llm_used = False
    async with httpx.AsyncClient() as client:
        result = await _call_kimi(client, user_content)

    if result is None:
        result = _heuristic_diagnosis(record, exception)
    else:
        llm_used = True

    # Build journal entry dict
    journal_dict = None
    if result.drafted_journal_entry:
        journal_dict = result.drafted_journal_entry.model_dump()

    # Persist to DB
    await db.execute(
        update(ExceptionItem)
        .where(ExceptionItem.exception_id == exception_id)
        .values(
            ai_diagnosis=result.diagnosis,
            recommended_action=result.recommended_action,
            drafted_journal_entry=journal_dict,
        )
    )

    return DiagnosticOut(
        exception_id=exception.exception_id,
        record_id=record.record_id,
        source_type=record.source_type,
        amount=float(record.amount),
        transaction_date=record.transaction_date,
        risk_score=exception.risk_score,
        ai_diagnosis=result.diagnosis,
        recommended_action=result.recommended_action,
        drafted_journal_entry=journal_dict,
        llm_used=llm_used,
    )


# ---------------------------------------------------------------------------
# Public: diagnose all PENDING exceptions in a batch
# ---------------------------------------------------------------------------
async def diagnose_batch_exceptions(
    db: AsyncSession,
    batch_id: uuid.UUID,
) -> BatchDiagnosticOut:
    """Run diagnostic agent on every PENDING ExceptionItem in the batch."""
    exc_result = await db.execute(
        select(ExceptionItem.exception_id)
        .where(
            ExceptionItem.batch_id == batch_id,
            ExceptionItem.status == "PENDING",
        )
        .order_by(ExceptionItem.risk_score)   # HIGH first
    )
    exception_ids = [row[0] for row in exc_result.all()]

    diagnosed: list[DiagnosticOut] = []
    for exc_id in exception_ids:
        result = await diagnose_exception(db, exc_id)
        if result:
            diagnosed.append(result)

    return BatchDiagnosticOut(
        batch_id=batch_id,
        diagnosed_count=len(diagnosed),
        items=diagnosed,
    )
