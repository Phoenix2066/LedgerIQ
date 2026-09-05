from collections.abc import AsyncGenerator
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings


# ---------------------------------------------------------------------------
# URL sanitizer — handles raw Neon/libpq connection strings gracefully
# ---------------------------------------------------------------------------
def _sanitize_database_url(url: str) -> str:
    """
    Ensure the DATABASE_URL is compatible with asyncpg:
      1. Force scheme to 'postgresql+asyncpg'
      2. Strip libpq-only params (sslmode, channel_binding) that crash asyncpg
      3. Keep 'ssl=require' for TLS
    """
    parsed = urlparse(url)

    # Fix scheme: postgresql:// → postgresql+asyncpg://
    scheme = parsed.scheme
    if scheme in ("postgresql", "postgres"):
        scheme = "postgresql+asyncpg"
    elif scheme in ("postgresql+psycopg2", "postgres+psycopg2"):
        scheme = "postgresql+asyncpg"

    # Strip libpq-only query params that asyncpg doesn't understand
    params = parse_qs(parsed.query, keep_blank_values=True)
    libpq_only = {"sslmode", "channel_binding", "connect_timeout", "application_name"}

    # Convert sslmode=require → ssl=require
    if "sslmode" in params and "ssl" not in params:
        params["ssl"] = params["sslmode"]

    for key in libpq_only:
        params.pop(key, None)

    clean_query = urlencode(params, doseq=True)
    clean_url = urlunparse((scheme, parsed.netloc, parsed.path,
                            parsed.params, clean_query, parsed.fragment))
    return clean_url


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
_db_url = _sanitize_database_url(settings.DATABASE_URL)

engine = create_async_engine(
    _db_url,
    echo=False,          # Set True for SQL query logging during development
    pool_pre_ping=True,  # Detect stale connections
    pool_size=5,
    max_overflow=10,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session; commit on success, rollback on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
