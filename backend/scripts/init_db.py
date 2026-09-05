"""
scripts/init_db.py
==================
One-time database initialisation script.

What it does:
  1. Connects to Neon Serverless PostgreSQL.
  2. Creates required extensions: uuid-ossp, pg_trgm.
  3. Drops all existing tables and recreates them cleanly from SQLAlchemy models.

Run from the backend/ directory:
    python scripts/init_db.py

WARNING: This will DROP and recreate all tables. Do NOT run on production data.
"""

import asyncio
import sys
from pathlib import Path

# Make sure `backend/` is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db.models import Base
from app.db.session import _sanitize_database_url


async def init_db() -> None:
    db_url = _sanitize_database_url(settings.DATABASE_URL)
    print(f"🔗 Connecting to: {db_url[:60]}...")

    engine = create_async_engine(
        db_url,
        echo=True,
        pool_pre_ping=True,
    )

    async with engine.begin() as conn:
        # ── Enable required PostgreSQL extensions ────────────────────────────
        print("📦 Creating extensions: uuid-ossp, pg_trgm...")
        await conn.execute(
            text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        )
        await conn.execute(
            text("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        )

        # ── Drop all tables and recreate from models ─────────────────────────
        print("🗑️  Dropping existing tables...")
        await conn.run_sync(Base.metadata.drop_all)

        print("🏗️  Creating all tables from SQLAlchemy models...")
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()

    print("\n✅ Database initialized successfully!")
    print("   Tables created:")
    for table in Base.metadata.sorted_tables:
        print(f"     • {table.name}")


if __name__ == "__main__":
    asyncio.run(init_db())
