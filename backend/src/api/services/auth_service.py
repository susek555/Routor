import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.exceptions.exceptions import InvalidCredentialsError, InvalidTokenError, UsernameAlreadyExistsError
from src.database.database import DbSession
from src.database.models import User
from src.database.query.auth import (
    create_refresh_token,
    create_user_with_token,
    get_active_user_by_id,
    get_active_user_by_username,
    get_user_by_username,
    get_valid_refresh_token,
    revoke_refresh_token,
)

TOKEN_TTL_DAYS = 365
bearer_scheme = HTTPBearer(auto_error=True)
BearerCredentials = Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]


class AuthService:
    """Handles password hashing, token lifecycle, and user authentication."""

    _password_hasher = PasswordHash.recommended()

    @classmethod
    def hash_password(cls, password: str) -> str:
        """Hashes a plain-text password using Argon2."""
        return cls._password_hasher.hash(password)

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain-text password against a stored hash."""
        return cls._password_hasher.verify(plain_password, hashed_password)

    @staticmethod
    def generate_raw_token() -> str:
        """Generates a cryptographically random URL-safe token."""
        return secrets.token_urlsafe(48)

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Returns a SHA-256 hex digest of a raw token for database storage."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @staticmethod
    def token_expiration(days: int = TOKEN_TTL_DAYS) -> datetime:
        """Calculates token expiration timestamp in UTC."""
        return datetime.now(UTC) + timedelta(days=days)

    @classmethod
    async def register_user(
        cls,
        session: AsyncSession,
        username: str,
        password: str,
    ) -> tuple[str, datetime]:
        """Registers a new user and issues an initial long-lived token."""
        normalized_username = username.strip()
        existing = await get_user_by_username(session, username=normalized_username)
        if existing:
            raise UsernameAlreadyExistsError()

        now = datetime.now(UTC)
        raw_token = cls.generate_raw_token()
        expires_at = cls.token_expiration()

        await create_user_with_token(
            session=session,
            username=normalized_username,
            password_hash=cls.hash_password(password),
            token_hash=cls.hash_token(raw_token),
            expires_at=expires_at,
            now=now,
        )
        return raw_token, expires_at

    @classmethod
    async def login_user(
        cls,
        session: AsyncSession,
        username: str,
        password: str,
    ) -> tuple[str, datetime]:
        """Authenticates user credentials and issues a new token."""
        normalized_username = username.strip()
        user = await get_active_user_by_username(session, username=normalized_username)
        if not user or not cls.verify_password(password, user.password_hash):
            raise InvalidCredentialsError()

        now = datetime.now(UTC)
        raw_token = cls.generate_raw_token()
        expires_at = cls.token_expiration()

        await create_refresh_token(
            session=session,
            user=user,
            token_hash=cls.hash_token(raw_token),
            expires_at=expires_at,
            now=now,
        )
        return raw_token, expires_at

    @classmethod
    async def logout_user(cls, session: AsyncSession, raw_token: str) -> None:
        """Revokes a single authentication token."""
        await revoke_refresh_token(
            session=session,
            token_hash=cls.hash_token(raw_token),
            revoked_at=datetime.now(UTC),
        )

    @classmethod
    async def resolve_user_from_token(cls, session: AsyncSession, raw_token: str) -> User | None:
        """Validates a raw token and returns the active user, or None if invalid."""
        now = datetime.now(UTC)
        token_row = await get_valid_refresh_token(
            session,
            token_hash=cls.hash_token(raw_token),
            now=now,
        )
        if not token_row:
            return None

        return await get_active_user_by_id(session, user_id=token_row.user_id)

    @classmethod
    async def get_current_user(
        cls,
        credentials: BearerCredentials,
        db: DbSession,
    ) -> User:
        """FastAPI dependency resolving the current user from a Bearer token."""
        user = await cls.resolve_user_from_token(db, credentials.credentials)
        if not user:
            raise InvalidTokenError()

        return user


CurrentUser = Annotated[User, Depends(AuthService.get_current_user)]
