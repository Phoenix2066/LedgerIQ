import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 1. ReconciliationBatch
# ---------------------------------------------------------------------------
class ReconciliationBatch(Base):
    """Represents a single reconciliation run over a batch of records."""

    __tablename__ = "reconciliation_batches"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exception_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    match_rate: Mapped[float] = mapped_column(
        Numeric(5, 2), default=0.0, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    records: Mapped[list["FinancialRecord"]] = relationship(
        "FinancialRecord", back_populates="batch", cascade="all, delete-orphan"
    )
    matches: Mapped[list["RecordMatch"]] = relationship(
        "RecordMatch", back_populates="batch", cascade="all, delete-orphan"
    )
    exceptions: Mapped[list["ExceptionItem"]] = relationship(
        "ExceptionItem", back_populates="batch", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 2. FinancialRecord
# ---------------------------------------------------------------------------
class FinancialRecord(Base):
    """A single ingested financial record from Bank, Gateway, or Invoice source."""

    __tablename__ = "financial_records"

    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'BANK' | 'GATEWAY' | 'INVOICE'
    raw_entity_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_entity_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    reference_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="UNMATCHED", nullable=False
    )  # 'MATCHED' | 'EXCEPTION' | 'UNMATCHED' | 'RESOLVED'
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    batch: Mapped["ReconciliationBatch"] = relationship(
        "ReconciliationBatch", back_populates="records"
    )
    matches_as_a: Mapped[list["RecordMatch"]] = relationship(
        "RecordMatch",
        foreign_keys="RecordMatch.record_a_id",
        back_populates="record_a",
        cascade="all, delete-orphan",
    )
    matches_as_b: Mapped[list["RecordMatch"]] = relationship(
        "RecordMatch",
        foreign_keys="RecordMatch.record_b_id",
        back_populates="record_b",
        cascade="all, delete-orphan",
    )
    exception_items: Mapped[list["ExceptionItem"]] = relationship(
        "ExceptionItem", back_populates="record", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# 3. RecordMatch
# ---------------------------------------------------------------------------
class RecordMatch(Base):
    """Stores a matched pair of FinancialRecords with confidence scoring."""

    __tablename__ = "record_matches"

    match_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
    )
    record_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_records.record_id", ondelete="CASCADE"),
        nullable=False,
    )
    record_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_records.record_id", ondelete="CASCADE"),
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False
    )  # 0.00 – 1.00
    match_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'EXACT' | 'FUZZY' | 'ONE_TO_MANY'
    reasoning_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    batch: Mapped["ReconciliationBatch"] = relationship(
        "ReconciliationBatch", back_populates="matches"
    )
    record_a: Mapped["FinancialRecord"] = relationship(
        "FinancialRecord", foreign_keys=[record_a_id], back_populates="matches_as_a"
    )
    record_b: Mapped["FinancialRecord"] = relationship(
        "FinancialRecord", foreign_keys=[record_b_id], back_populates="matches_as_b"
    )


# ---------------------------------------------------------------------------
# 4. ExceptionItem
# ---------------------------------------------------------------------------
class ExceptionItem(Base):
    """Unmatched / anomalous records queued for human-in-the-loop review."""

    __tablename__ = "exceptions"

    exception_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_records.record_id", ondelete="CASCADE"),
        nullable=False,
    )
    risk_score: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # 'HIGH' | 'MEDIUM' | 'LOW'
    ai_diagnosis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    drafted_journal_entry: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="PENDING", nullable=False
    )  # 'PENDING' | 'APPROVED' | 'REJECTED'
    resolved_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    batch: Mapped["ReconciliationBatch"] = relationship(
        "ReconciliationBatch", back_populates="exceptions"
    )
    record: Mapped["FinancialRecord"] = relationship(
        "FinancialRecord", back_populates="exception_items"
    )


# ---------------------------------------------------------------------------
# 5. DynamicRule  (Phase 3 — Adaptive Rule Synthesis)
# ---------------------------------------------------------------------------
class DynamicRule(Base):
    """
    Adaptive matching rules synthesised from human-approved exceptions.

    rule_type values:
      REGEX_STRIP  — strip a noise prefix/suffix from raw_entity_name
      VENDOR_MAP   — map a raw entity alias to its canonical normalized name
      FEE_TOLERANCE — override the gateway fee tolerance band for a vendor
    """

    __tablename__ = "dynamic_rules"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'REGEX_STRIP' | 'VENDOR_MAP' | 'FEE_TOLERANCE'
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    action_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

# ---------------------------------------------------------------------------
# 6. AuditLog  (Phase 4 — Append-Only Tamper-Proof Audit Trail)
# ---------------------------------------------------------------------------
class AuditLog(Base):
    """
    Immutable append-only audit trail. Never updated, never deleted.

    action_type values:
      AUTO_MATCH          — Tier 1/2/3 reconciler made a match
      EXCEPTION_FLAGGED   — record placed in exception pool after triage
      EXCEPTION_DIAGNOSED — LLM or heuristic diagnosis attached
      HUMAN_APPROVED      — human controller approved an exception
      HUMAN_REJECTED      — human controller rejected an exception
      RULE_SYNTHESIZED    — adaptive DynamicRule created from approval
      RULE_APPLIED        — DynamicRule applied during pre-Tier-1 hook
      FORECAST_GENERATED  — cash runway forecast computed
      SIMULATION_RUN      — what-if scenario simulation executed
    """

    __tablename__ = "audit_logs"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    batch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reconciliation_batches.batch_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_records.record_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    reasoning_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changes_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
