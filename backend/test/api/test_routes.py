import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import src.api.auth as auth_module
import src.api.routes as routes_module
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from src.api.auth import router as auth_router
from src.api.exceptions.exceptions import (
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
)
from src.api.exceptions.exceptions_handler import setup_exception_handlers
from src.api.routes import routes_router
from src.database.database import get_db

AUTH_MODULE_PATH = auth_module.__name__
ROUTES_MODULE_PATH = routes_module.__name__
AUTH_SERVICE_PATH = "src.api.services.auth_service.AuthService"


@pytest.fixture
def app():
    """FastAPI test application containing auth and routes routers with exception handlers."""
    test_app = FastAPI()
    setup_exception_handlers(test_app)
    test_app.include_router(auth_router)
    test_app.include_router(routes_router)
    return test_app


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def auth_headers():
    """Default Bearer authorization header for protected route tests."""
    return {"Authorization": "Bearer test-valid-token"}


@pytest.fixture
def valid_generate_payload():
    return {
        "center": {"latitude": 52.2297, "longitude": 21.0122},
        "target_distance": 10000.0,
        "fcm_token": "token_abc_123",
    }


@pytest.fixture
def valid_credentials_payload():
    return {
        "username": "runner_one",
        "password": "secret-password-123",
    }


class TestRegisterEndpoint:
    @patch(f"{AUTH_MODULE_PATH}.AuthService.register_user", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_register_success_returns_201(
        self,
        mock_register_user,
        app,
        mock_db_session,
        valid_credentials_payload,
    ):
        """Verifies that POST /auth/register creates a user and returns a token with 201 status."""
        expires_at = datetime.now(UTC) + timedelta(days=365)
        mock_register_user.return_value = ("raw-register-token", expires_at)
        app.dependency_overrides[get_db] = lambda: mock_db_session

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/auth/register", json=valid_credentials_payload)

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["token"] == "raw-register-token"
            assert data["token_type"] == "bearer"
            assert "expires_at" in data

            mock_register_user.assert_awaited_once_with(
                session=mock_db_session,
                username=valid_credentials_payload["username"],
                password=valid_credentials_payload["password"],
            )
        finally:
            app.dependency_overrides.clear()

    @patch(f"{AUTH_MODULE_PATH}.AuthService.register_user", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_register_duplicate_username_returns_409(
        self,
        mock_register_user,
        app,
        mock_db_session,
        valid_credentials_payload,
    ):
        """Verifies that registering an existing username returns 409 Conflict."""
        mock_register_user.side_effect = UsernameAlreadyExistsError()
        app.dependency_overrides[get_db] = lambda: mock_db_session

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/auth/register", json=valid_credentials_payload)

            assert response.status_code == status.HTTP_409_CONFLICT
            assert response.json()["detail"] == "Username is already taken"
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_register_invalid_payload_returns_422(self, app):
        """Verifies that missing or invalid fields return 422 Unprocessable Entity."""
        invalid_payload = {"username": "ab"}  # Missing password and too short username

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/auth/register", json=invalid_payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoginEndpoint:
    @patch(f"{AUTH_MODULE_PATH}.AuthService.login_user", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_login_success_returns_200(
        self,
        mock_login_user,
        app,
        mock_db_session,
        valid_credentials_payload,
    ):
        """Verifies that POST /auth/login authenticates valid credentials and returns 200."""
        expires_at = datetime.now(UTC) + timedelta(days=365)
        mock_login_user.return_value = ("raw-login-token", expires_at)
        app.dependency_overrides[get_db] = lambda: mock_db_session

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/auth/login", json=valid_credentials_payload)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["token"] == "raw-login-token"
            assert data["token_type"] == "bearer"
            assert "expires_at" in data

            mock_login_user.assert_awaited_once_with(
                session=mock_db_session,
                username=valid_credentials_payload["username"],
                password=valid_credentials_payload["password"],
            )
        finally:
            app.dependency_overrides.clear()

    @patch(f"{AUTH_MODULE_PATH}.AuthService.login_user", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_login_invalid_credentials_returns_401(
        self,
        mock_login_user,
        app,
        mock_db_session,
        valid_credentials_payload,
    ):
        """Verifies that invalid credentials return 401 Unauthorized."""
        mock_login_user.side_effect = InvalidCredentialsError()
        app.dependency_overrides[get_db] = lambda: mock_db_session

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/auth/login", json=valid_credentials_payload)

            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            assert response.json()["detail"] == "Invalid username or password"
        finally:
            app.dependency_overrides.clear()


class TestLogoutEndpoint:
    @patch(f"{AUTH_MODULE_PATH}.AuthService.logout_user", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_logout_success_returns_204(
        self,
        mock_logout_user,
        app,
        mock_db_session,
    ):
        """Verifies that POST /auth/logout revokes the token and returns 204 No Content."""
        app.dependency_overrides[get_db] = lambda: mock_db_session
        raw_token = "raw-token-to-revoke"

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/auth/logout", json={"token": raw_token})

            assert response.status_code == status.HTTP_204_NO_CONTENT
            mock_logout_user.assert_awaited_once_with(
                session=mock_db_session,
                raw_token=raw_token,
            )
        finally:
            app.dependency_overrides.clear()


class TestGenerateRouteEndpoint:
    @pytest.mark.asyncio
    async def test_generate_route_missing_token_returns_401_or_403(self, app, valid_generate_payload):
        """Verifies that POST /routes/generate rejects unauthenticated requests."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/routes/generate", json=valid_generate_payload)

        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    @patch(f"{AUTH_SERVICE_PATH}.resolve_user_from_token", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_generate_route_invalid_token_returns_401(
        self,
        mock_resolve_user,
        app,
        mock_db_session,
        auth_headers,
        valid_generate_payload,
    ):
        """Verifies that an invalid or expired token returns 401 Unauthorized."""
        mock_resolve_user.return_value = None
        app.dependency_overrides[get_db] = lambda: mock_db_session

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/routes/generate",
                    headers=auth_headers,
                    json=valid_generate_payload,
                )

            assert response.status_code == status.HTTP_401_UNAUTHORIZED
        finally:
            app.dependency_overrides.clear()

    @patch(f"{ROUTES_MODULE_PATH}.RouteService.dispatch")
    @patch(f"{AUTH_SERVICE_PATH}.resolve_user_from_token", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_generate_route_success_returns_202(
        self,
        mock_resolve_user,
        mock_dispatch,
        app,
        mock_db_session,
        auth_headers,
        valid_generate_payload,
    ):
        """Verifies that POST /routes/generate returns 202 ACCEPTED, task_id, and passes current user ID."""
        current_user_id = uuid.uuid4()
        mock_resolve_user.return_value = MagicMock(id=current_user_id, is_deleted=False)
        expected_task_id = "task-uuid-9876"
        mock_dispatch.return_value = expected_task_id
        app.dependency_overrides[get_db] = lambda: mock_db_session

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/routes/generate",
                    headers=auth_headers,
                    json=valid_generate_payload,
                )

            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert data["task_id"] == expected_task_id

            mock_dispatch.assert_called_once()
            called_payload = mock_dispatch.call_args[0][0]
            assert called_payload.center.latitude == valid_generate_payload["center"]["latitude"]
            assert called_payload.center.longitude == valid_generate_payload["center"]["longitude"]
            assert called_payload.target_distance == valid_generate_payload["target_distance"]
            assert called_payload.fcm_token == valid_generate_payload["fcm_token"]
            assert mock_dispatch.call_args.kwargs["user_id"] == current_user_id
        finally:
            app.dependency_overrides.clear()

    @patch(f"{AUTH_SERVICE_PATH}.resolve_user_from_token", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_generate_route_invalid_payload_returns_422(
        self,
        mock_resolve_user,
        app,
        mock_db_session,
        auth_headers,
    ):
        """Verifies that missing mandatory fields return 422 Unprocessable Entity."""
        mock_resolve_user.return_value = MagicMock(id=uuid.uuid4(), is_deleted=False)
        app.dependency_overrides[get_db] = lambda: mock_db_session
        invalid_payload = {
            "center": {"latitude": 52.2297},  # Missing longitude
            "target_distance": 5000.0,
        }

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/routes/generate",
                    headers=auth_headers,
                    json=invalid_payload,
                )

            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()


class TestGetTaskRoutesEndpoint:
    @pytest.mark.asyncio
    async def test_get_task_routes_missing_token_returns_401_or_403(self, app):
        """Verifies that GET /routes/{task_id} rejects unauthenticated requests."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/routes/test-task-123")

        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    @patch(f"{ROUTES_MODULE_PATH}.get_route_variants_by_task_id")
    @patch(f"{AUTH_SERVICE_PATH}.resolve_user_from_token", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_task_routes_success_with_variants(
        self,
        mock_resolve_user,
        mock_get_variants,
        app,
        mock_db_session,
        auth_headers,
    ):
        """Verifies that GET /routes/{task_id} fetches records from DB and formats response."""
        task_id = "test-task-variant-123"
        mock_resolve_user.return_value = MagicMock(id=uuid.uuid4(), is_deleted=False)
        app.dependency_overrides[get_db] = lambda: mock_db_session

        # Mock database entities matching RouteVariantResponse schema
        mock_variant_1 = MagicMock()
        mock_variant_1.id = uuid.uuid4()
        mock_variant_1.variant_index = 1
        mock_variant_1.distance_meters = 10050
        mock_variant_1.fitness_score = 0.94
        mock_variant_1.geojson = {
            "type": "LineString",
            "coordinates": [[21.01, 52.22], [21.02, 52.23]],
        }

        mock_variant_2 = MagicMock()
        mock_variant_2.id = uuid.uuid4()
        mock_variant_2.variant_index = 2
        mock_variant_2.distance_meters = 9980
        mock_variant_2.fitness_score = 0.91
        mock_variant_2.geojson = {
            "type": "LineString",
            "coordinates": [[21.01, 52.22], [21.03, 52.24]],
        }

        mock_get_variants.return_value = [mock_variant_1, mock_variant_2]

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get(f"/routes/{task_id}", headers=auth_headers)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["task_id"] == task_id
            assert data["total_variants"] == 2
            assert len(data["variants"]) == 2

            assert data["variants"][0]["variant_index"] == 1
            assert data["variants"][0]["distance_meters"] == 10050
            assert data["variants"][0]["fitness_score"] == pytest.approx(0.94)

            mock_get_variants.assert_awaited_once_with(mock_db_session, task_id)
        finally:
            app.dependency_overrides.clear()

    @patch(f"{ROUTES_MODULE_PATH}.get_route_variants_by_task_id")
    @patch(f"{AUTH_SERVICE_PATH}.resolve_user_from_token", new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_task_routes_empty_results(
        self,
        mock_resolve_user,
        mock_get_variants,
        app,
        mock_db_session,
        auth_headers,
    ):
        """Verifies that a task with no variants returns total_variants=0 and an empty list."""
        task_id = "task-without-routes"
        mock_resolve_user.return_value = MagicMock(id=uuid.uuid4(), is_deleted=False)
        app.dependency_overrides[get_db] = lambda: mock_db_session
        mock_get_variants.return_value = []

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get(f"/routes/{task_id}", headers=auth_headers)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["task_id"] == task_id
            assert data["total_variants"] == 0
            assert data["variants"] == []

            mock_get_variants.assert_awaited_once_with(mock_db_session, task_id)
        finally:
            app.dependency_overrides.clear()
