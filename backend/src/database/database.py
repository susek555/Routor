import os
from collections.abc import AsyncGenerator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

# 1. Database connection configuration from environment variables
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
POSTGRES_DB = os.getenv("POSTGRES_DB")

# Base URL (takes precedence if DATABASE_URL is explicitly set)
RAW_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
)

# Driver-specific database URLs
ASYNC_DATABASE_URL = RAW_DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
SYNC_DATABASE_URL = RAW_DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


# 2. Base ORM declarative model
class Base(DeclarativeBase):
    pass


# 3. Async engine & session for FastAPI (asyncpg)
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool,  # Prevents connection pool issues across forks and container restarts
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection session generator for FastAPI endpoints."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# 4. Sync engine & session for Celery workers (psycopg2)
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool,  # Disables connection pooling to prevent sharing sockets across Celery forks
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@contextmanager
def get_sync_db():
    """Context manager providing a transactional sync session for Celery tasks."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# async def get_dummies():
#     async with AsyncSessionLocal() as session:
#         async with session.begin():
#             result = await session.execute(text("SELECT * FROM dummy"))
#             return result.mappings().all()


# async def get_single_dummy_message():
#     async with AsyncSessionLocal() as session:
#         async with session.begin():
#             result = await session.execute(text("SELECT * FROM dummy LIMIT 1"))
#             row = result.mappings().one_or_none()
#             if row is not None:
#                 return row["message"]

#             return None
