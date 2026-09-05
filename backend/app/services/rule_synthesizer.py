"""
rule_synthesizer.py
====================
Adaptive rule synthesis engine — extracts reusable matching patterns from
human-approved exceptions and persists them as DynamicRule rows.

Rule types generated:
  REGEX_STRIP   — strip a noisy prefix/suffix from raw_entity_name before matching
  VENDOR_MAP    — map a raw entity alias to a canonical normalized name
  FEE_TOLERANCE — override the gateway fee rate tolerance for a specific vendor
"""

import logging
import re
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DynamicRule, ExceptionItem, FinancialRecord

logger = logging.getLogger(__name__)

# Known gateway prefixes to detect REGEX_STRIP candidates
_GATEWAY_PREFIXES = re.compile(
    r"^(RZP\*|PAY-|NEFT-|IMPS-|UPI-|TXN-|INV-|LUMP-|FUZ-)",
    re.IGNORECASE,
)

# Known vendor suffix noise
_SUFFIX_NOISE = re.compile(
    r"\s+(PVT\.?|LTD\.?|LLC|INC\.?|CORP\.?|CO\.?|INDIA|BLR|MUM|DEL|HYD|SOLN|LOGSTCS)\.?$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Pattern extractor
# ---------------------------------------------------------------------------
def extract_pattern(
    record: FinancialRecord,
    exception: ExceptionItem,
) -> Optional[tuple[str, str, dict]]:
    """
    Analyse a resolved FinancialRecord and return a tuple of:
      (rule_type, pattern, action_payload)
    or None if no useful rule can be extracted.
    """
    raw = record.raw_entity_name or ""
    normalized = record.normalized_entity_name or ""
    meta = record.metadata_json or {}
    anomaly = meta.get("anomaly_type", "")

    # ── REGEX_STRIP: entity has a known gateway prefix ────────────────────────
    prefix_match = _GATEWAY_PREFIXES.match(raw)
    if prefix_match:
        prefix = prefix_match.group(1)
        return (
            "REGEX_STRIP",
            f"^{re.escape(prefix)}",
            {
                "description": f"Strip gateway prefix '{prefix}' from raw entity names",
                "example_raw": raw,
                "example_normalized": normalized or raw[len(prefix):],
            },
        )

    # ── VENDOR_MAP: normalized name differs from raw ──────────────────────────
    if normalized and normalized.upper() != raw.upper() and len(normalized) > 2:
        return (
            "VENDOR_MAP",
            raw.upper(),
            {
                "canonical_name": normalized,
                "description": f"Map '{raw}' → '{normalized}'",
                "source_type": record.source_type,
            },
        )

    # ── FEE_TOLERANCE: gateway with fee discrepancy anomaly ───────────────────
    if anomaly == "fee_discrepancy_gt_2pct" and record.source_type == "GATEWAY":
        gross = float(meta.get("gross_amount", 0))
        fee = float(meta.get("gateway_fee", 0))
        if gross > 0:
            effective_rate = round(fee / gross, 4)
            return (
                "FEE_TOLERANCE",
                normalized or raw,
                {
                    "observed_fee_rate": effective_rate,
                    "tolerance_min": max(0.01, effective_rate - 0.005),
                    "tolerance_max": effective_rate + 0.005,
                    "description": f"Custom fee tolerance for '{normalized or raw}': {effective_rate:.2%}",
                },
            )

    # ── Fallback: suffix noise ────────────────────────────────────────────────
    suffix_match = _SUFFIX_NOISE.search(raw)
    if suffix_match and normalized:
        suffix = suffix_match.group(1)
        return (
            "REGEX_STRIP",
            f"{re.escape(suffix.strip())}$",
            {
                "description": f"Strip trailing suffix '{suffix.strip()}' from entity names",
                "example_raw": raw,
                "example_normalized": normalized,
            },
        )

    return None


# ---------------------------------------------------------------------------
# Save rule to DB
# ---------------------------------------------------------------------------
async def synthesize_and_save(
    db: AsyncSession,
    exception: ExceptionItem,
    record: FinancialRecord,
) -> Optional[DynamicRule]:
    """
    Extract a pattern from the resolved record and persist a DynamicRule.
    Returns the created DynamicRule or None if no pattern could be extracted.
    """
    result = extract_pattern(record, exception)
    if result is None:
        logger.info(
            "No rule pattern extractable from exception %s (record=%s, entity='%s')",
            exception.exception_id,
            record.record_id,
            record.raw_entity_name,
        )
        return None

    rule_type, pattern, action_payload = result
    rule_name = f"auto:{rule_type.lower()}:{pattern[:40]}"

    rule = DynamicRule(
        rule_id=uuid.uuid4(),
        rule_name=rule_name,
        rule_type=rule_type,
        pattern=pattern,
        action_payload={
            **action_payload,
            "synthesized_from_exception": str(exception.exception_id),
            "synthesized_from_record": str(record.record_id),
        },
    )
    db.add(rule)

    logger.info(
        "Synthesized DynamicRule: type=%s pattern='%s' from exception=%s",
        rule_type,
        pattern,
        exception.exception_id,
    )
    return rule
