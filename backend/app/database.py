"""
SQLite Database Configuration

Manages SQLite database connection using SQLAlchemy async engine.
Provides session management and database initialization.
"""

import logging
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import MetaData

logger = logging.getLogger(__name__)

# Database file path
DATABASE_DIR = Path(__file__).parent.parent.parent / "data"
DATABASE_PATH = DATABASE_DIR / "AgentTwister.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models"""
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
    future=True,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.

    Yields:
        AsyncSession: Database session for the request
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize the database.

    Creates all tables if they don't exist.
    """
    # Ensure data directory exists
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        # Import all models to ensure they are registered
        from app.models import payload_sqlalchemy  # noqa: F401
        from app.models import evidence_bundle_sqlalchemy  # noqa: F401

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

    logger.info(f"Database initialized at {DATABASE_PATH}")


async def close_db() -> None:
    """
    Close the database connection.
    """
    await engine.dispose()
    logger.info("Database connection closed")


def get_database_path() -> Path:
    """Get the path to the SQLite database file"""
    return DATABASE_PATH
