import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import routers and dependencies
import src.api.routes as routes_module
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from src.api.routes import routes_router
from src.database.database import get_db

MODULE_PATH = routes_module.__name__


@pytest.fixture
def app():
    """Isolated FastAPI test application containing only the routes router."""
    test_app = FastAPI()
    test_app.include_router(routes_router)
    return test_app


@pytest.fixture
def mock_db_session():
    return AsyncMock()


@pytest.fixture
def valid_generate_payload():
    return {
        "user_id": str(uuid.uuid4()),
        "center": {"latitude": 52.2297, "longitude": 21.0122},
        "target_distance": 10000.0,
        "fcm_token": "token_abc_123",
    }


class TestGenerateRouteEndpoint:
    @patch(f"{MODULE_PATH}.RouteService.dispatch")
    @pytest.mark.asyncio
    async def test_generate_route_success_returns_202(
        self,
        mock_dispatch,
        app,
        valid_generate_payload,
    ):
        """Verifies that POST /routes/generate returns 202 ACCEPTED and task_id."""
        expected_task_id = "task-uuid-9876"
        mock_dispatch.return_value = expected_task_id

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/routes/generate", json=valid_generate_payload)

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["task_id"] == expected_task_id

        mock_dispatch.assert_called_once()
        called_payload = mock_dispatch.call_args[0][0]
        assert str(called_payload.user_id) == valid_generate_payload["user_id"]
        assert called_payload.center.latitude == valid_generate_payload["center"]["latitude"]
        assert called_payload.center.longitude == valid_generate_payload["center"]["longitude"]
        assert called_payload.target_distance == valid_generate_payload["target_distance"]

    @pytest.mark.asyncio
    async def test_generate_route_invalid_payload_returns_422(self, app):
        """Verifies that missing mandatory fields return 422 Unprocessable Entity."""
        invalid_payload = {
            "center": {"latitude": 52.2297},  # Missing longitude and user_id
            "target_distance": 5000.0,
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/routes/generate", json=invalid_payload)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetTaskRoutesEndpoint:
    @patch(f"{MODULE_PATH}.get_route_variants_by_task_id")
    @pytest.mark.asyncio
    async def test_get_task_routes_success_with_variants(
        self,
        mock_get_variants,
        app,
        mock_db_session,
    ):
        """Verifies that GET /routes/{task_id} fetches records from DB and formats response."""
        task_id = "test-task-variant-123"
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
                response = await client.get(f"/routes/{task_id}")

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

    @patch(f"{MODULE_PATH}.get_route_variants_by_task_id")
    @pytest.mark.asyncio
    async def test_get_task_routes_empty_results(
        self,
        mock_get_variants,
        app,
        mock_db_session,
    ):
        """Verifies that a task with no variants returns total_variants=0 and an empty list."""
        task_id = "task-without-routes"
        app.dependency_overrides[get_db] = lambda: mock_db_session
        mock_get_variants.return_value = []

        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get(f"/routes/{task_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            assert data["task_id"] == task_id
            assert data["total_variants"] == 0
            assert data["variants"] == []

            mock_get_variants.assert_awaited_once_with(mock_db_session, task_id)
        finally:
            app.dependency_overrides.clear()
