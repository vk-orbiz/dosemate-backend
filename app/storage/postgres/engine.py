"""Async SQLAlchemy engine and session factory. The only place the driver URL is derived."""

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import Pool


def to_async_url(url: str) -> str:
    """`postgresql://...` (what Settings holds) -> `postgresql+asyncpg://...`."""
    parsed = make_url(url)
    if parsed.drivername in ("postgresql", "postgres"):
        parsed = parsed.set(drivername="postgresql+asyncpg")
    return parsed.render_as_string(hide_password=False)


def build_engine(
    url: str, *, min_size: int = 1, max_size: int = 10, poolclass: type[Pool] | None = None
) -> AsyncEngine:
    """Lazy: no connection is opened until first use."""
    if poolclass is not None:  # e.g. NullPool for one-shot migration runs
        return create_async_engine(to_async_url(url), poolclass=poolclass)
    return create_async_engine(
        to_async_url(url),
        pool_size=min_size,
        max_overflow=max(max_size - min_size, 0),
        pool_pre_ping=True,
    )


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: rows are converted to domain models after commit.
    return async_sessionmaker(engine, expire_on_commit=False)
