"""
schemas/audit.py
=================
Pydantic v2 schemas for audit trail endpoints.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    audit_id: uuid.UUID
    batch_id: uuid.UUID
    record_id: Optional[uuid.UUID]
    action_type: str
    actor: str
    confidence_score: Optional[float]
    reasoning_snapshot: Optional[str]
    changes_payload: Optional[dict]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditTrailOut(BaseModel):
    batch_id: uuid.UUID
    total_events: int
    events: list[AuditLogOut]


class AuditExportOut(BaseModel):
    batch_id: uuid.UUID
    format: str        # 'json' | 'csv'
    total_events: int
    exported_at: datetime
    payload: str       # JSON string or CSV string
