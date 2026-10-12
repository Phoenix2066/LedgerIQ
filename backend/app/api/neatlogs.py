"""
app/api/neatlogs.py
===================
API Router for NeatLogs — Live Structured Logging & Telemetry Endpoint.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Query

from app.neatlogs import neatlogs

router = APIRouter(prefix="/api/neatlogs", tags=["NeatLogs"])


@router.get("", response_model=List[Dict[str, Any]], summary="Get live NeatLogs system stream")
async def get_neat_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    category: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    """Returns the latest in-memory NeatLogs entries for live system monitoring."""
    return neatlogs.get_logs(limit=limit, category=category)


@router.post("/clear", summary="Clear NeatLogs in-memory buffer")
async def clear_neat_logs() -> Dict[str, str]:
    """Clears the live log stream buffer."""
    neatlogs.clear()
    neatlogs.info("NeatLogs", "Log buffer cleared by user request.")
    return {"status": "cleared"}
