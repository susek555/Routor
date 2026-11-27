import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.api.exceptions.exceptions import (
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
)
from src.api.services.auth_service import AuthService

MODULE_PATH = "src.api.services.auth_service"


class TestAuthServiceHashingAndTokens:
    def test_hash_and_verify_password(self):
        """Verifies Argon2 password hashing and verification."""
        plain = "super-secret-password"
        hashed = AuthService.hash_password(plain)

        assert hashed != plain
        assert AuthService.verify_password(plain, hashed) is True
        assert AuthService.verify_password("wrong-password", hashed) is False

    def test_generate_and_hash_token(self):
        """Verifies raw token generation and deterministic SHA-256 hashing."""
        raw_token = AuthService.generate_raw_token()
        first_hash = AuthService.hash_token(raw_token)
        second_hash = AuthService.hash_token(raw_token)

        assert isinstance(raw_token, str) and len(raw_token) > 20
        assert first_hash == second_hash
        assert first_hash != raw_token


class TestAuthServiceFlows:
    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.create_user_with_token", new_callable=AsyncMock)
    @patch(f"{MODULE_PATH}.get_user_by_username", new_callable=AsyncMock)
    async def test_register_user_success(self, mock_get_user, mock_create_user):
        """Verifies user creation and token generation for a new username."""
        mock_get_user.return_value = None
        session = AsyncMock()

        raw_token, expires_at = await AuthService.register_user(
            session=session,
            username="  runner_one  ",
            password="password123",
        )

        assert raw_token
        assert expires_at > datetime.now(UTC) + timedelta(days=360)
        mock_get_user.assert_awaited_once_with(session, username="runner_one")
        mock_create_user.assert_awaited_once()
        assert mock_create_user.await_args.kwargs["username"] == "runner_one"

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.get_user_by_username", new_callable=AsyncMock)
    async def test_register_user_duplicate_raises(self, mock_get_user):
        """Verifies UsernameAlreadyExistsError when username already exists."""
        mock_get_user.return_value = MagicMock(username="runner_one")
        session = AsyncMock()

        with pytest.raises(UsernameAlreadyExistsError):
            await AuthService.register_user(
                session=session,
                username="runner_one",
                password="password123",
            )

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.create_refresh_token", new_callable=AsyncMock)
    @patch(f"{MODULE_PATH}.get_active_user_by_username", new_callable=AsyncMock)
    async def test_login_user_success(self, mock_get_active_user, mock_create_token):
        """Verifies login for an active user with valid credentials."""
        password_hash = AuthService.hash_password("password123")
        user = MagicMock(id=uuid.uuid4(), username="runner_one", password_hash=password_hash)
        mock_get_active_user.return_value = user
        session = AsyncMock()

        raw_token, expires_at = await AuthService.login_user(
            session=session,
            username="runner_one",
            password="password123",
        )

        assert raw_token
        assert expires_at > datetime.now(UTC)
        mock_create_token.assert_awaited_once()

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.get_active_user_by_username", new_callable=AsyncMock)
    async def test_login_user_invalid_password_raises(self, mock_get_active_user):
        """Verifies InvalidCredentialsError when password does not match."""
        password_hash = AuthService.hash_password("password123")
        user = MagicMock(id=uuid.uuid4(), username="runner_one", password_hash=password_hash)
        mock_get_active_user.return_value = user
        session = AsyncMock()

        with pytest.raises(InvalidCredentialsError):
            await AuthService.login_user(
                session=session,
                username="runner_one",
                password="wrong-password",
            )

    @pytest.mark.asyncio
    @patch(f"{MODULE_PATH}.revoke_refresh_token", new_callable=AsyncMock)
    async def test_logout_user_revokes_token(self, mock_revoke):
        """Verifies logout hashes raw token and revokes it in DB."""
        session = AsyncMock()
        raw_token = "sample-raw-token"

        await AuthService.logout_user(session=session, raw_token=raw_token)

        mock_revoke.assert_awaited_once()
        assert mock_revoke.await_args.kwargs["token_hash"] == AuthService.hash_token(raw_token)
        assert mock_revoke.await_args.kwargs["revoked_at"] is not None
