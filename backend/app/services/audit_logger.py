"""
services/audit_logger.py
=========================
Append-only, tamper-proof audit trail service.

Design guarantees:
  - AuditLog rows are INSERT-only — no UPDATE, no DELETE.
  - log_event() must be called WITHIN the same AsyncSession transaction as
    the primary state change, ensuring atomicity (Execution Requirement #1).
  - Provides typed factory methods for each event category for consistency.

Usage:
    # Inside an endpoint, within the same db session:
    await AuditLogger.log_event(
        db=db,
        batch_id=batch_id,
        record_id=record.record_id,
        action_type="AUTO_MATCH",
        actor="SYSTEM_RECONCILER",
        confidence_score=1.0,
        reasoning_snapshot="Exact reference + amount + date match.",
        changes_payload={"before": "UNMATCHED", "after": "MATCHED"},
    )
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


class AuditLogger:
    """Namespace for audit logging factory methods."""

    @staticmethod
    async def log_event(
        db: AsyncSession,
        batch_id: uuid.UUID,
        action_type: str,
        actor: str,
        record_id: Optional[uuid.UUID] = None,
        confidence_score: Optional[float] = None,
        reasoning_snapshot: Optional[str] = None,
        changes_payload: Optional[dict] = None,
    ) -> AuditLog:
        """
        Insert an immutable AuditLog row in the current session.

        Call this BEFORE db.commit() within the same transaction.
        The log entry is flushed with the primary record changes atomically.
        """
        entry = AuditLog(
            audit_id=uuid.uuid4(),
            batch_id=batch_id,
            record_id=record_id,
            action_type=action_type,
            actor=actor,
            confidence_score=(
                round(float(confidence_score), 4) if confidence_score is not None else None
            ),
            reasoning_snapshot=reasoning_snapshot,
            changes_payload=changes_payload,
        )
        db.add(entry)
        return entry

    # ── Typed factory helpers ─────────────────────────────────────────────────

    @staticmethod
    async def log_auto_match(
        db: AsyncSession,
        batch_id: uuid.UUID,
        record_a_id: uuid.UUID,
        record_b_id: uuid.UUID,
        match_type: str,
        confidence_score: float,
        reasoning: str,
    ) -> AuditLog:
        return await AuditLogger.log_event(
            db=db,
            batch_id=batch_id,
            record_id=record_a_id,
            action_type="AUTO_MATCH",
            actor="SYSTEM_RECONCILER",
            confidence_score=confidence_score,
            reasoning_snapshot=f"[{match_type}] {reasoning}",
            changes_payload={
                "match_type": match_type,
                "record_a": str(record_a_id),
                "record_b": str(record_b_id),
                "before": "UNMATCHED",
                "after": "MATCHED",
            },
        )

    @staticmethod
    async def log_exception_flagged(
        db: AsyncSession,
        batch_id: uuid.UUID,
        record_id: uuid.UUID,
        risk_score: str,
        diagnosis: str,
    ) -> AuditLog:
        return await AuditLogger.log_event(
            db=db,
            batch_id=batch_id,
            record_id=record_id,
            action_type="EXCEPTION_FLAGGED",
            actor="SYSTEM_RECONCILER",
            reasoning_snapshot=f"Risk: {risk_score}. {diagnosis}",
            changes_payload={"risk_score": risk_score, "before": "UNMATCHED", "after": "EXCEPTION"},
        )

    @staticmethod
    async def log_exception_diagnosed(
        db: AsyncSession,
        batch_id: uuid.UUID,
        record_id: uuid.UUID,
        llm_used: bool,
        diagnosis: str,
        recommended_action: str,
    ) -> AuditLog:
        return await AuditLogger.log_event(
            db=db,
            batch_id=batch_id,
            record_id=record_id,
            action_type="EXCEPTION_DIAGNOSED",
            actor="DIAGNOSTIC_AGENT",
            reasoning_snapshot=f"llm_used={llm_used}. Diagnosis: {diagnosis}",
            changes_payload={
                "llm_used": llm_used,
                "diagnosis": diagnosis,
                "recommended_action": recommended_action,
            },
        )

    @staticmethod
    async def log_human_action(
        db: AsyncSession,
        batch_id: uuid.UUID,
        record_id: uuid.UUID,
        action: str,          # 'APPROVED' | 'REJECTED'
        resolved_by: str,
    ) -> AuditLog:
        action_type = "HUMAN_APPROVED" if action == "APPROVED" else "HUMAN_REJECTED"
        return await AuditLogger.log_event(
            db=db,
            batch_id=batch_id,
            record_id=record_id,
            action_type=action_type,
            actor="CONTROLLER_HUMAN",
            reasoning_snapshot=f"Resolved by: {resolved_by}",
            changes_payload={
                "action": action,
                "resolved_by": resolved_by,
                "before": "PENDING",
                "after": action,
            },
        )

    @staticmethod
    async def log_rule_synthesized(
        db: AsyncSession,
        batch_id: uuid.UUID,
        record_id: uuid.UUID,
        rule_id: uuid.UUID,
        rule_name: str,
        rule_type: str,
        pattern: str,
    ) -> AuditLog:
        return await AuditLogger.log_event(
            db=db,
            batch_id=batch_id,
            record_id=record_id,
            action_type="RULE_SYNTHESIZED",
            actor="RULE_SYNTHESIZER",
            reasoning_snapshot=f"Created rule '{rule_name}' [{rule_type}] pattern='{pattern}'",
            changes_payload={
                "rule_id": str(rule_id),
                "rule_name": rule_name,
                "rule_type": rule_type,
                "pattern": pattern,
            },
        )

    @staticmethod
    async def log_forecast(
        db: AsyncSession,
        batch_id: uuid.UUID,
        horizon_days: int,
        baseline_cash: float,
        days_to_zero: Optional[int],
    ) -> AuditLog:
        return await AuditLogger.log_event(
            db=db,
            batch_id=batch_id,
            action_type="FORECAST_GENERATED",
            actor="FORECASTER",
            reasoning_snapshot=f"30-day runway forecast. C0=₹{baseline_cash:,.2f}, days_to_zero={days_to_zero}",
            changes_payload={
                "horizon_days": horizon_days,
                "baseline_cash": round(baseline_cash, 2),
                "days_to_zero": days_to_zero,
            },
        )

    @staticmethod
    async def log_simulation(
        db: AsyncSession,
        batch_id: uuid.UUID,
        delay_days: int,
        default_rate: float,
        gateway_fee_surge: float,
        summary: str,
    ) -> AuditLog:
        return await AuditLogger.log_event(
            db=db,
            batch_id=batch_id,
            action_type="SIMULATION_RUN",
            actor="FORECASTER",
            reasoning_snapshot=summary,
            changes_payload={
                "delay_days": delay_days,
                "default_rate": default_rate,
                "gateway_fee_surge": gateway_fee_surge,
            },
        )
