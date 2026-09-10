"""Database service - handles database connections and sessions."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

# Database URL - in production, this would come from environment variables
DATABASE_URL = "sqlite+aiosqlite:///./app.db"

# Create async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create session maker
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def init_db():
    """Initialize database - create tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connection."""
    await engine.dispose()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session with context manager."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def get_db_session() -> AsyncSession:
    """Get database session (for synchronous contexts)."""
    return AsyncSessionLocal()