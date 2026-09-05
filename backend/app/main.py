"""
app/main.py
===========
FastAPI application entry point for the AI Finance Controller backend.
Standardized location inside app/ package.

Run locally:
    cd backend
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    # or
    python run.py
"""

from contextlib import asynccontextmanager
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.ingestion import router as ingestion_router
from app.api.reconciliation import router as reconciliation_router
from app.api.copilot import router as copilot_router
from app.api.exceptions import router as exceptions_router
from app.api.forecasting import router as forecasting_router
from app.api.audit import router as audit_router


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown hooks)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown handlers."""
    print("🚀 AI Finance Controller backend starting up...")
    yield
    print("🛑 AI Finance Controller backend shutting down...")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Finance Controller",
    description=(
        "Razorpay Buildathon Track 04 — Agentic multi-source reconciliation, "
        "exception triaging, and cash forecasting backend."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow all origins for seamless plain HTML/CSS/JS frontend calls
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(ingestion_router)
app.include_router(reconciliation_router)
app.include_router(copilot_router)
app.include_router(exceptions_router)
app.include_router(forecasting_router)
app.include_router(audit_router)


# ---------------------------------------------------------------------------
# Health check — verifies DB connectivity and LLM config
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Health"], summary="Liveness + readiness probe")
async def health_check() -> dict:
    """
    Returns service status including:
    - DB: whether the PostgreSQL connection pool is responsive
    - LLM: whether KIMI_API_KEY is configured
    """
    from app.db.session import AsyncSessionLocal
    from app.config import settings

    t0 = time.perf_counter()
    db_status = "unknown"
    db_error = None
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        db_status = "error"
        db_error = str(exc)

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    llm_configured = bool(settings.KIMI_API_KEY)

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "service": "ai-finance-controller",
        "db": db_status,
        "db_error": db_error,
        "llm_configured": llm_configured,
        "llm_model": settings.KIMI_MODEL if llm_configured else None,
        "db_latency_ms": elapsed_ms,
    }
