from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import RefreshToken, User


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """Fetches a user by username."""
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_user_by_username(session: AsyncSession, username: str) -> User | None:
    """Fetches a non-deleted user by username."""
    stmt = select(User).where(
        User.username == username,
        User.is_deleted.is_(False),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_user_by_id(session: AsyncSession, user_id) -> User | None:
    """Fetches a non-deleted user by ID."""
    stmt = select(User).where(
        User.id == user_id,
        User.is_deleted.is_(False),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_user_with_token(
    session: AsyncSession,
    username: str,
    password_hash: str,
    token_hash: str,
    expires_at: datetime,
    now: datetime,
) -> User:
    """Creates a new user and issues an initial refresh token."""
    user = User(
        username=username,
        password_hash=password_hash,
        last_login_at=now,
    )
    session.add(user)
    await session.flush()  # Populate user.id before creating token row

    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(refresh_token)
    await session.commit()
    return user


async def create_refresh_token(
    session: AsyncSession,
    user: User,
    token_hash: str,
    expires_at: datetime,
    now: datetime,
) -> None:
    """Updates last login timestamp and stores a new refresh token."""
    user.last_login_at = now
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(refresh_token)
    await session.commit()


async def revoke_refresh_token(
    session: AsyncSession,
    token_hash: str,
    revoked_at: datetime,
) -> None:
    """Marks an active refresh token as revoked."""
    stmt = select(RefreshToken).where(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
    )
    result = await session.execute(stmt)
    token_row = result.scalar_one_or_none()
    if token_row:
        token_row.revoked_at = revoked_at
        await session.commit()


async def get_valid_refresh_token(
    session: AsyncSession,
    token_hash: str,
    now: datetime,
) -> RefreshToken | None:
    """Fetches a non-revoked and non-expired refresh token."""
    stmt = select(RefreshToken).where(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > now,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
