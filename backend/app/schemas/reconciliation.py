import uuid
from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Risk distribution breakdown
# ---------------------------------------------------------------------------
class RiskBreakdown(BaseModel):
    high: int
    medium: int
    low: int


# ---------------------------------------------------------------------------
# Reconciliation run — immediate trigger response
# ---------------------------------------------------------------------------
class ReconciliationRunOut(BaseModel):
    batch_id: uuid.UUID
    status: str                   # 'COMPLETED' | 'ALREADY_RECONCILED' | 'NO_RECORDS'
    total_records: int
    matched_count: int
    exception_count: int
    match_rate: float             # percentage 0.0–100.0
    tier1_exact: int
    tier2_one_to_many: int
    tier3_fuzzy: int
    risk_breakdown: RiskBreakdown


# ---------------------------------------------------------------------------
# Batch summary — GET endpoint
# ---------------------------------------------------------------------------
class ReconciliationSummaryOut(BaseModel):
    batch_id: uuid.UUID
    total_records: int
    matched_count: int
    exception_count: int
    unmatched_count: int
    match_rate: float
    risk_breakdown: RiskBreakdown

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Single exception item
# ---------------------------------------------------------------------------
class ExceptionOut(BaseModel):
    exception_id: uuid.UUID
    record_id: uuid.UUID
    source_type: str
    raw_entity_name: str
    normalized_entity_name: Optional[str]
    amount: float
    reference_code: Optional[str]
    transaction_date: date
    risk_score: str               # 'HIGH' | 'MEDIUM' | 'LOW'
    ai_diagnosis: Optional[str]
    recommended_action: Optional[str]
    status: str                   # 'PENDING' | 'APPROVED' | 'REJECTED'

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Paginated exception list
# ---------------------------------------------------------------------------
class ExceptionListOut(BaseModel):
    batch_id: uuid.UUID
    total: int
    risk_filter: Optional[str]
    items: list[ExceptionOut]
