import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Financial Record
# ---------------------------------------------------------------------------
class FinancialRecordOut(BaseModel):
    """Serialised view of a single FinancialRecord row."""

    record_id: uuid.UUID
    batch_id: uuid.UUID
    source_type: str
    raw_entity_name: str
    normalized_entity_name: Optional[str]
    amount: float
    reference_code: Optional[str]
    transaction_date: date
    status: str
    metadata_json: Optional[dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Batch responses
# ---------------------------------------------------------------------------
class BatchSummaryOut(BaseModel):
    """Returned immediately after generate-synthetic completes ingestion."""

    batch_id: uuid.UUID
    total_records: int
    bank_count: int
    gateway_count: int
    invoice_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BatchRecordsOut(BaseModel):
    """Paginated list of records belonging to a batch."""

    batch_id: uuid.UUID
    total_records: int
    records: list[FinancialRecordOut]
