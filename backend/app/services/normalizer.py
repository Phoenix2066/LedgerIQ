"""
normalizer.py
=============
Async entity normalizer that cleans raw merchant / entity name strings using:

  Primary  → Local Ollama LLM (phi4-mini / llama3.2) via httpx
  Fallback → Regex-based stripping if Ollama is offline or times out

Usage:
    from app.services.normalizer import normalize_entity_name, normalize_batch

    clean = await normalize_entity_name("RZP*ACME-TECH-BLR")
    # → "Acme Tech"
"""

import asyncio
import json
import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regex fallback normalizer
# ---------------------------------------------------------------------------
_STRIP_PREFIXES = re.compile(
    r"^(RZP\*|PAY-|NEFT-|IMPS-|UPI-|TXN-|INV-|LUMP-|FUZ-)",
    re.IGNORECASE,
)
_CLEAN_SEPARATORS = re.compile(r"[-_*|/\\]+")
_COLLAPSE_SPACES = re.compile(r"\s{2,}")
_STRIP_SUFFIXES = re.compile(
    r"\s+(PVT\.?|LTD\.?|LLC|INC\.?|CORP\.?|CO\.?|INDIA|BLR|MUM|DEL|HYD)\.?$",
    re.IGNORECASE,
)


def _regex_normalize(raw: str) -> str:
    """Best-effort regex normaliser — strips payment prefixes, separators, and legal suffixes."""
    text = raw.strip().upper()
    text = _STRIP_PREFIXES.sub("", text)
    text = _CLEAN_SEPARATORS.sub(" ", text)
    text = _STRIP_SUFFIXES.sub("", text)
    text = _COLLAPSE_SPACES.sub(" ", text).strip().title()
    return text or raw  # never return empty string


# ---------------------------------------------------------------------------
# Ollama LLM normalizer
# ---------------------------------------------------------------------------
_OLLAMA_PROMPT = """\
You are a financial data cleaner. Extract the clean corporate entity name from the raw merchant string.
Rules:
  - Remove payment gateway prefixes like RZP*, PAY-, NEFT-, UPI-, IMPS-
  - Remove location suffixes (BLR, MUM, DEL, HYD, INDIA)
  - Correct obvious typos (LOGSTCS → Logistics, SOLN → Solutions)
  - Normalize case to Title Case
  - Return ONLY valid JSON: {{"normalized_name": "<clean name>"}}

Raw merchant string: "{raw}"
"""


async def _ollama_normalize(client: httpx.AsyncClient, raw: str) -> str | None:
    """
    Call local Ollama /api/generate and parse the normalized_name from JSON.
    Returns None on any error (timeout, offline, bad JSON).
    """
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": _OLLAMA_PROMPT.format(raw=raw),
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0},
    }
    try:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=settings.OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        body = resp.json()
        result = json.loads(body.get("response", "{}"))
        name = result.get("normalized_name", "").strip()
        return name if name else None
    except (httpx.TimeoutException, httpx.ConnectError):
        logger.warning("Ollama unavailable — falling back to regex for: %s", raw)
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Ollama response parse error (%s) for: %s", exc, raw)
        return None


_NORM_CACHE: dict[str, str] = {}
_SEMAPHORE = asyncio.Semaphore(8)


async def _is_ollama_online(client: httpx.AsyncClient) -> bool:
    """Quick 300ms probe to check if Ollama server is running."""
    try:
        resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/version", timeout=0.3)
        return resp.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def normalize_entity_name(raw: str) -> str:
    """
    Normalize a single raw entity name string.
    Tries in-memory cache first, then Ollama, then regex fallback.
    """
    if raw in _NORM_CACHE:
        return _NORM_CACHE[raw]

    async with httpx.AsyncClient() as client:
        if await _is_ollama_online(client):
            async with _SEMAPHORE:
                result = await _ollama_normalize(client, raw)
                if result:
                    _NORM_CACHE[raw] = result
                    return result

    cleaned = _regex_normalize(raw)
    _NORM_CACHE[raw] = cleaned
    return cleaned


async def normalize_batch(raw_names: list[str]) -> list[str]:
    """
    Concurrently normalize a list of raw entity name strings with caching and deduplication.
    Re-uses a single httpx client across all unique requests for efficiency.
    """
    if not raw_names:
        return []

    # Find unique uncached names
    uncached_unique = [name for name in set(raw_names) if name not in _NORM_CACHE]

    if uncached_unique:
        async with httpx.AsyncClient() as client:
            online = await _is_ollama_online(client)
            if not online:
                for name in uncached_unique:
                    _NORM_CACHE[name] = _regex_normalize(name)
            else:
                async def _normalize_one(n: str):
                    async with _SEMAPHORE:
                        res = await _ollama_normalize(client, n)
                        _NORM_CACHE[n] = res if res else _regex_normalize(n)

                await asyncio.gather(*[_normalize_one(n) for n in uncached_unique])

    # Return results in original order from cache
    return [_NORM_CACHE.get(raw, _regex_normalize(raw)) for raw in raw_names]
