"""
Database Session Management

Async SQLAlchemy session with PostgreSQL.
"""

import ssl
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from archon_prime.api.config import settings

# Module-level engine (created lazily)
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker] = None


def _get_ssl_context():
    """Create SSL context for cloud PostgreSQL."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def get_engine() -> AsyncEngine:
    """Get or create the database engine."""
    global _engine

    if _engine is None:
        url = settings.DATABASE_URL
        print(f"[DB] Creating engine with URL: {url[:60]}...")

        # Detect cloud PostgreSQL (Neon, Supabase)
        connect_args = {}
        if "neon.tech" in url or "supabase" in url:
            print("[DB] Detected cloud PostgreSQL, enabling SSL context")
            connect_args["ssl"] = _get_ssl_context()

        _engine = create_async_engine(
            url,
            echo=settings.DATABASE_ECHO,
            poolclass=NullPool,
            connect_args=connect_args,
        )

    return _engine


def get_session_maker() -> async_sessionmaker:
    """Get or create the session maker."""
    global _async_session_maker

    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    return _async_session_maker


async def init_db() -> None:
    """Initialize database connection."""
    from archon_prime.api.db.models import Base

    engine = get_engine()
    print("[DB] Initializing database connection...")

    async with engine.begin() as conn:
        # Create tables if they don't exist (dev only)
        # In production, use Alembic migrations
        if settings.DEBUG:
            print("[DB] Creating tables (DEBUG mode)...")
            await conn.run_sync(Base.metadata.create_all)
            print("[DB] Tables created successfully")


async def close_db() -> None:
    """Close database connection."""
    global _engine, _async_session_maker

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        print("[DB] Database connection closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.

    Usage in FastAPI:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
