from collections.abc import AsyncGenerator
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import os

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.neatlogs import neatlogs


def _sanitize_database_url(url: str) -> str:
    """Ensure DATABASE_URL is compatible with asyncpg or sqlite."""
    if url.startswith("sqlite"):
        return url

    parsed = urlparse(url)
    scheme = parsed.scheme
    if scheme in ("postgresql", "postgres", "postgresql+psycopg2", "postgres+psycopg2"):
        scheme = "postgresql+asyncpg"

    params = parse_qs(parsed.query, keep_blank_values=True)
    libpq_only = {"sslmode", "channel_binding", "connect_timeout", "application_name"}

    if "sslmode" in params and "ssl" not in params:
        params["ssl"] = params["sslmode"]

    for key in libpq_only:
        params.pop(key, None)

    clean_query = urlencode(params, doseq=True)
    return urlunparse((scheme, parsed.netloc, parsed.path, parsed.params, clean_query, parsed.fragment))


_primary_db_url = _sanitize_database_url(settings.DATABASE_URL)
_sqlite_fallback_url = "sqlite+aiosqlite:///./ledgeriq.db"

try:
    if _primary_db_url.startswith("sqlite"):
        engine = create_async_engine(_primary_db_url, echo=False)
        neatlogs.info("Database", "Using local SQLite database engine")
    else:
        engine = create_async_engine(
            _primary_db_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        neatlogs.info("Database", f"Configured Async Engine for PostgreSQL: {_primary_db_url[:40]}...")
except Exception as exc:
    neatlogs.warn("Database", f"Failed to initialize PostgreSQL engine: {exc}. Falling back to SQLite.")
    engine = create_async_engine(_sqlite_fallback_url, echo=False)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session; fallback to SQLite automatically if primary DB connection fails."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as err:
            await session.rollback()
            neatlogs.error("Database", f"Session error: {err}")
            raise
        finally:
            await session.close()
