import uuid
from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Journal Entry (drafted by AI)
# ---------------------------------------------------------------------------
class JournalEntrySchema(BaseModel):
    debit_account: str
    credit_account: str
    amount: float
    memo: str

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount(cls, v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0


# ---------------------------------------------------------------------------
# LLM diagnostic response (parsed from kimi JSON output)
# ---------------------------------------------------------------------------
class DiagnosticLLMResponse(BaseModel):
    """Strict parse of what the LLM returns. Has safe fallback defaults."""

    diagnosis: str = "Unable to determine root cause. Manual review required."
    recommended_action: str = "Escalate to senior controller."
    drafted_journal_entry: Optional[JournalEntrySchema] = None

    model_config = ConfigDict(extra="ignore")


# ---------------------------------------------------------------------------
# API response after diagnosing an exception
# ---------------------------------------------------------------------------
class DiagnosticOut(BaseModel):
    exception_id: uuid.UUID
    record_id: uuid.UUID
    source_type: str
    amount: float
    transaction_date: date
    risk_score: str
    ai_diagnosis: str
    recommended_action: str
    drafted_journal_entry: Optional[dict]
    llm_used: bool   # False if heuristic fallback was used

    model_config = ConfigDict(from_attributes=True)


class BatchDiagnosticOut(BaseModel):
    batch_id: uuid.UUID
    diagnosed_count: int
    items: list[DiagnosticOut]


# ---------------------------------------------------------------------------
# Exception action (approve / reject)
# ---------------------------------------------------------------------------
class ExceptionActionRequest(BaseModel):
    action: str                   # 'APPROVE' | 'REJECT'
    synthesize_rule: bool = False
    resolved_by: str = "controller"

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        v = v.upper()
        if v not in ("APPROVE", "REJECT"):
            raise ValueError("action must be 'APPROVE' or 'REJECT'")
        return v


class ExceptionActionOut(BaseModel):
    exception_id: uuid.UUID
    action_taken: str
    new_status: str
    record_status: str
    rule_synthesized: bool
    rule_name: Optional[str]
