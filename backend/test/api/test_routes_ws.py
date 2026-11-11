import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import src.api.routes_ws as ws_module
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient
from src.api.routes_ws import (
    _cleanup_redis,
    _extract_state,
    _is_ack_message,
    wait_for_client_ack,
    ws_router,
)

MODULE_PATH = ws_module.__name__


@pytest.fixture
def app():
    test_app = FastAPI()
    test_app.include_router(ws_router)
    return test_app


@pytest.fixture
def client(app):
    return TestClient(app)


# ==============================================================================
# 1. HELPER FUNCTIONS UNIT TESTS
# ==============================================================================


class TestWebSocketHelpers:
    @pytest.mark.parametrize(
        "msg, expected",
        [
            ("ACK", True),
            ("ack", True),
            ("  ACK  \n", True),
            ('{"action": "ACK"}', True),
            ('{"action": "ack"}', False),
            ('{"action": "PING"}', False),
            ("INVALID_PAYLOAD", False),
            ("{invalid_json", False),
        ],
    )
    def test_is_ack_message(self, msg: str, expected: bool):
        """Verifies text and JSON ACK payload recognition."""
        assert _is_ack_message(msg) is expected

    @pytest.mark.parametrize(
        "raw_json, expected_state",
        [
            ('{"state": "COMPLETED", "payload": {}}', "COMPLETED"),
            ('{"state": "LOADING_GRAPH"}', "LOADING_GRAPH"),
            ('{"no_state": 123}', None),
            ("not-a-json", None),
        ],
    )
    def test_extract_state(self, raw_json: str, expected_state: str | None):
        """Verifies safe JSON parsing and state extraction."""
        assert _extract_state(raw_json) == expected_state

    @pytest.mark.asyncio
    async def test_cleanup_redis_success(self):
        """Verifies proper unsubscribe and connection closing on cleanup."""
        mock_pubsub = AsyncMock()
        mock_redis = AsyncMock()

        await _cleanup_redis(mock_pubsub, mock_redis, "routes:task-1", "task-1")

        mock_pubsub.unsubscribe.assert_awaited_once_with("routes:task-1")
        mock_pubsub.close.assert_awaited_once()
        mock_redis.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_redis_swallows_and_logs_exception(self):
        """Verifies that cleanup does not propagate errors if connection was already closed."""
        mock_pubsub = AsyncMock()
        mock_redis = AsyncMock()
        mock_pubsub.unsubscribe.side_effect = ConnectionError("Redis connection dropped")

        # Must not raise an exception
        await _cleanup_redis(mock_pubsub, mock_redis, "routes:task-1", "task-1")
        mock_pubsub.unsubscribe.assert_awaited_once()


# ==============================================================================
# 2. CLIENT ACK RECEIPT UNIT TESTS
# ==============================================================================


class TestWaitForClientAck:
    @pytest.mark.asyncio
    async def test_wait_for_client_ack_with_text(self):
        """Verifies loop breaks immediately when simple ACK text arrives."""
        mock_ws = AsyncMock()
        mock_ws.receive_text.side_effect = ["random-msg", "ACK"]

        await wait_for_client_ack(mock_ws, "task-123")

        assert mock_ws.receive_text.call_count == 2

    @pytest.mark.asyncio
    async def test_wait_for_client_ack_with_json_action(self):
        """Verifies loop breaks when JSON action ACK arrives."""
        mock_ws = AsyncMock()
        mock_ws.receive_text.side_effect = ['{"action": "ACK"}']

        await wait_for_client_ack(mock_ws, "task-123")

        mock_ws.receive_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_wait_for_client_ack_handles_disconnect(self):
        """Verifies WebSocketDisconnect is handled gracefully without re-raising."""
        mock_ws = AsyncMock()
        mock_ws.receive_text.side_effect = WebSocketDisconnect(code=1000)

        await wait_for_client_ack(mock_ws, "task-123")
        mock_ws.receive_text.assert_awaited_once()


# ==============================================================================
# 3. WEBSOCKET INTEGRATION TESTS (FLOW & RACE CONDITIONS)
# ==============================================================================


class TestWebSocketRouteStatusFlow:
    @patch(f"{MODULE_PATH}.aioredis.from_url")
    def test_ws_cached_terminal_state_closes_after_ack(
        self,
        mock_redis_from_url,
        client,
    ):
        """Verifies race condition where task completed before client connects."""
        task_id = "task-cached-completed"
        terminal_payload = json.dumps({"state": "COMPLETED"})

        mock_redis_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis_client.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis_from_url.return_value = mock_redis_client
        mock_redis_client.get.return_value = terminal_payload

        with client.websocket_connect(f"/routes/ws/{task_id}") as ws:
            received_msg = ws.receive_text()
            assert received_msg == terminal_payload

            ws.send_text("ACK")

            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_text()
            assert exc_info.value.code == 1000

        mock_redis_client.get.assert_awaited_once_with(f"routes:state:{task_id}")
        mock_redis_client.close.assert_awaited_once()

    @patch(f"{MODULE_PATH}.aioredis.from_url")
    def test_ws_realtime_events_flow_and_ack(
        self,
        mock_redis_from_url,
        client,
    ):
        """Verifies initial state check followed by real-time pubsub stream and ACK closing."""
        task_id = "task-realtime-flow"
        initial_cache_payload = json.dumps({"state": "LOADING_GRAPH"})
        terminal_event = json.dumps({"state": "COMPLETED"})

        mock_redis_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis_client.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis_from_url.return_value = mock_redis_client

        mock_redis_client.get.return_value = initial_cache_payload

        mock_pubsub.get_message.side_effect = [
            None,
            {"type": "message", "data": terminal_event},
        ]

        with client.websocket_connect(f"/routes/ws/{task_id}") as ws:
            msg1 = ws.receive_text()
            assert msg1 == initial_cache_payload

            msg2 = ws.receive_text()
            assert msg2 == terminal_event

            ws.send_text('{"action": "ACK"}')

            with pytest.raises(WebSocketDisconnect) as exc_info:
                ws.receive_text()
            assert exc_info.value.code == 1000

        mock_pubsub.subscribe.assert_awaited_once_with(f"routes:{task_id}")
        mock_pubsub.unsubscribe.assert_awaited_once_with(f"routes:{task_id}")

    @patch(f"{MODULE_PATH}.aioredis.from_url")
    def test_ws_client_disconnect_triggers_cleanup(
        self,
        mock_redis_from_url,
        client,
    ):
        """Verifies that client disconnection during streaming safely triggers Redis cleanup."""
        task_id = "task-client-disconnects"

        mock_redis_client = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis_client.pubsub = MagicMock(return_value=mock_pubsub)
        mock_redis_from_url.return_value = mock_redis_client

        mock_redis_client.get.return_value = None
        mock_pubsub.get_message.return_value = None

        with client.websocket_connect(f"/routes/ws/{task_id}") as ws:
            ws.close()

        mock_pubsub.unsubscribe.assert_awaited_once_with(f"routes:{task_id}")
        mock_pubsub.close.assert_awaited_once()
        mock_redis_client.close.assert_awaited_once()
