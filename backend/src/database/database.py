import os
from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://routor_user:routor_password@localhost:5432/routor_database",
).replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool
    )
AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_dummies():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(text("SELECT * FROM dummy"))
            return result.mappings().all()


async def get_single_dummy_message():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(text("SELECT * FROM dummy LIMIT 1"))
            row = result.mappings().one_or_none()
            if row is not None:
                return row["message"]

            return None
