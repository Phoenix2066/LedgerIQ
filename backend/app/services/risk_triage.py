"""
risk_triage.py
==============
Financial Risk Triage Matrix — classifies records that remain UNMATCHED
after the 3-tier reconciliation cascade and generates ExceptionItem rows.

Risk scoring rules (in priority order):
  HIGH   → amount > ₹25,000  OR  record aging > 7 days
  MEDIUM → ₹5,000 ≤ amount ≤ ₹25,000  OR  fee discrepancy detected in metadata > 2%
  LOW    → amount < ₹5,000  OR  rounding difference < ₹100
"""

import logging
import uuid
from datetime import date

from app.db.models import ExceptionItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Risk thresholds (₹)
# ---------------------------------------------------------------------------
HIGH_AMOUNT_THRESHOLD = 25_000.0
MEDIUM_AMOUNT_LOW = 5_000.0
MEDIUM_AMOUNT_HIGH = 25_000.0
LOW_ROUNDING_THRESHOLD = 100.0
HIGH_AGING_DAYS = 7
FEE_DISCREPANCY_THRESHOLD = 0.02   # > 2%


# ---------------------------------------------------------------------------
# Risk classifier
# ---------------------------------------------------------------------------

def _classify_risk(
    amount: float,
    transaction_date: date,
    metadata_json: dict | None,
    reference_date: date | None = None,
) -> tuple[str, str, str]:
    """
    Returns (risk_score, ai_diagnosis, recommended_action).
    reference_date defaults to today if not provided.
    """
    ref_date = reference_date or date.today()
    aging_days = (ref_date - transaction_date).days

    # Check for fee discrepancy in metadata (gateway records carry this)
    meta = metadata_json or {}
    fee_discrepancy = False
    if "gateway_fee" in meta and "gross_amount" in meta:
        gross = float(meta["gross_amount"])
        fee = float(meta["gateway_fee"])
        if gross > 0:
            effective_rate = fee / gross
            fee_discrepancy = effective_rate > FEE_DISCREPANCY_THRESHOLD

    # Check metadata anomaly hints (from synthetic generator)
    anomaly_type = meta.get("anomaly_type", "")
    risk_hint = meta.get("risk_hint", "")

    # ── HIGH risk ────────────────────────────────────────────────────────────
    if amount > HIGH_AMOUNT_THRESHOLD or aging_days > HIGH_AGING_DAYS:
        reasons = []
        if amount > HIGH_AMOUNT_THRESHOLD:
            reasons.append(f"transaction amount ₹{amount:,.2f} exceeds ₹25,000 threshold")
        if aging_days > HIGH_AGING_DAYS:
            reasons.append(f"record is {aging_days} days old (> 7-day aging limit)")
        if anomaly_type:
            reasons.append(f"anomaly type: {anomaly_type}")

        diagnosis = (
            f"High-risk unmatched transaction: {'; '.join(reasons)}. "
            "Requires immediate controller review."
        )
        action = "Escalate to senior controller for manual verification and journal entry."
        return "HIGH", diagnosis, action

    # ── MEDIUM risk ──────────────────────────────────────────────────────────
    if (MEDIUM_AMOUNT_LOW <= amount <= MEDIUM_AMOUNT_HIGH) or fee_discrepancy:
        reasons = []
        if MEDIUM_AMOUNT_LOW <= amount <= MEDIUM_AMOUNT_HIGH:
            reasons.append(f"amount ₹{amount:,.2f} falls in mid-range ₹5,000–₹25,000")
        if fee_discrepancy:
            reasons.append("gateway fee discrepancy exceeds 2% threshold detected")
        if anomaly_type:
            reasons.append(f"anomaly type: {anomaly_type}")

        diagnosis = (
            f"Medium-risk unmatched transaction: {'; '.join(reasons)}. "
            "Likely a timing or partial payment issue."
        )
        action = "Review against pending invoices; check for split payments or delayed settlements."
        return "MEDIUM", diagnosis, action

    # ── LOW risk ─────────────────────────────────────────────────────────────
    is_rounding = amount < LOW_ROUNDING_THRESHOLD
    reasons = []
    if is_rounding:
        reasons.append(f"minor amount ₹{amount:,.2f} — likely rounding discrepancy")
    if not reasons:
        reasons.append(f"amount ₹{amount:,.2f} below ₹5,000 low-risk threshold")
    if anomaly_type:
        reasons.append(f"anomaly type: {anomaly_type}")

    diagnosis = (
        f"Low-risk unmatched transaction: {'; '.join(reasons)}. "
        "May self-resolve or require minor adjustment."
    )
    action = "Schedule for end-of-month batch review; no immediate action required."
    return "LOW", diagnosis, action


# ---------------------------------------------------------------------------
# Public triage function
# ---------------------------------------------------------------------------

def triage_exceptions(
    unmatched_records: list,   # list of _Rec dataclass instances
    batch_id: uuid.UUID,
    reference_date: date | None = None,
) -> list[ExceptionItem]:
    """
    Classifies each unmatched record and returns a list of ExceptionItem ORM
    objects ready for bulk DB insert.

    Parameters
    ----------
    unmatched_records : list[_Rec]
        Records that remain UNMATCHED after all reconciliation tiers.
    batch_id : UUID
        The current batch identifier.
    reference_date : date, optional
        Used for aging calculation; defaults to today.
    """
    exception_items: list[ExceptionItem] = []

    for rec in unmatched_records:
        risk_score, ai_diagnosis, recommended_action = _classify_risk(
            amount=rec.amount,
            transaction_date=rec.transaction_date,
            metadata_json=rec.metadata_json,
            reference_date=reference_date,
        )

        logger.debug(
            "EXCEPTION [%s]: record=%s amount=%.2f risk=%s",
            rec.source_type,
            rec.record_id,
            rec.amount,
            risk_score,
        )

        exception_items.append(
            ExceptionItem(
                exception_id=uuid.uuid4(),
                batch_id=batch_id,
                record_id=rec.record_id,
                risk_score=risk_score,
                ai_diagnosis=ai_diagnosis,
                recommended_action=recommended_action,
                drafted_journal_entry=None,   # Phase 3: Agentic reasoning will fill this
                status="PENDING",
                resolved_by=None,
                resolved_at=None,
            )
        )

    return exception_items
