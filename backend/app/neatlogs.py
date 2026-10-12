"""
app/neatlogs.py
===============
NeatLogs — High-Performance Structured Logger & Live Event Buffer
Integrated for LedgerIQ | CFO.AI
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

# Ensure UTF-8 output encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

logger = logging.getLogger("neatlogs")
logger.setLevel(logging.INFO)

# In-memory ring buffer for live log streaming to UI
_LOG_BUFFER: List[Dict[str, Any]] = []
_MAX_BUFFER_SIZE = 1000


class NeatLogger:
    """Structured NeatLogs logger for system, DB, AI, and reconciliation events."""

    @staticmethod
    def _log(level: str, category: str, message: str, meta: Dict[str, Any] = None) -> Dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "category": category,
            "message": message,
            "meta": meta or {},
            "source": "neatlogs"
        }
        
        _LOG_BUFFER.append(entry)
        if len(_LOG_BUFFER) > _MAX_BUFFER_SIZE:
            _LOG_BUFFER.pop(0)
            
        icon = {
            "INFO": "[INFO]",
            "SUCCESS": "[OK]",
            "WARN": "[WARN]",
            "ERROR": "[ERR]",
            "RECON": "[RECON]",
            "AI_DECISION": "[AI]",
            "AUDIT": "[AUDIT]"
        }.get(level, "[LOG]")

        out_str = f"[NeatLogs][{entry['timestamp'][:19]}][{level}][{category}] {icon} {message}"
        try:
            print(out_str)
        except UnicodeEncodeError:
            print(out_str.encode("ascii", errors="replace").decode("ascii"))
            
        return entry

    @classmethod
    def info(cls, category: str, message: str, meta: Dict[str, Any] = None):
        return cls._log("INFO", category, message, meta)

    @classmethod
    def success(cls, category: str, message: str, meta: Dict[str, Any] = None):
        return cls._log("SUCCESS", category, message, meta)

    @classmethod
    def warn(cls, category: str, message: str, meta: Dict[str, Any] = None):
        return cls._log("WARN", category, message, meta)

    @classmethod
    def error(cls, category: str, message: str, meta: Dict[str, Any] = None):
        return cls._log("ERROR", category, message, meta)

    @classmethod
    def recon(cls, message: str, meta: Dict[str, Any] = None):
        return cls._log("RECON", "ReconciliationEngine", message, meta)

    @classmethod
    def ai(cls, message: str, meta: Dict[str, Any] = None):
        return cls._log("AI_DECISION", "CFO.AI", message, meta)

    @classmethod
    def audit(cls, message: str, meta: Dict[str, Any] = None):
        return cls._log("AUDIT", "AuditChain", message, meta)

    @classmethod
    def get_logs(cls, limit: int = 200, category: str = None) -> List[Dict[str, Any]]:
        logs = _LOG_BUFFER
        if category:
            logs = [l for l in logs if l["category"].lower() == category.lower()]
        return logs[-limit:]

    @classmethod
    def clear(cls):
        _LOG_BUFFER.clear()


neatlogs = NeatLogger()
