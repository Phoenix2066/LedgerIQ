"""
schemas/base.py
===============
Standardized JSON response envelope for all AI Finance Controller endpoints.

Every API response wraps its payload in:
  {
    "status":  "success" | "error",
    "data":    { ... },          # the actual response payload
    "message": "Optional info",
    "meta":    { "execution_time_ms": 142 }
  }

Usage in endpoints:
    from app.schemas.base import ok, err
    return ok(data=result, message="Reconciliation complete", elapsed_ms=42.1)
"""

import time
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MetaBlock(BaseModel):
    execution_time_ms: Optional[float] = None


class ApiResponse(BaseModel, Generic[T]):
    status: str = "success"
    data: Optional[T] = None
    message: Optional[str] = None
    meta: Optional[MetaBlock] = None


class ErrorResponse(BaseModel):
    status: str = "error"
    data: None = None
    message: str
    meta: Optional[MetaBlock] = None


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def ok(
    data: Any = None,
    message: Optional[str] = None,
    elapsed_ms: Optional[float] = None,
) -> dict:
    """Return a standardized success response dict."""
    return {
        "status": "success",
        "data": data,
        "message": message,
        "meta": {"execution_time_ms": round(elapsed_ms, 2) if elapsed_ms is not None else None},
    }


def err(
    message: str,
    elapsed_ms: Optional[float] = None,
) -> dict:
    """Return a standardized error response dict."""
    return {
        "status": "error",
        "data": None,
        "message": message,
        "meta": {"execution_time_ms": round(elapsed_ms, 2) if elapsed_ms is not None else None},
    }


class Timer:
    """Simple wall-clock timer for measuring endpoint execution time."""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000
