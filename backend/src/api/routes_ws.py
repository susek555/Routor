import asyncio
import json
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.data.task_state import TaskStateEnum
from src.generate_routes.worker_app import REDIS_URL, ws_channel_prefix, ws_state_key_prefix

logger = logging.getLogger(__name__)
ws_router = APIRouter(prefix="/routes", tags=["WebSocket"])
TERMINAL_STATES = {TaskStateEnum.COMPLETED, TaskStateEnum.FAILED}
ACK_MESSAGE = "ACK"  # Standard acknowledgment message from client


async def wait_for_client_ack(websocket: WebSocket, task_id: str) -> None:
    """Wait for the client to acknowledge receipt or disconnect gracefully."""
    logger.info(f"Terminal state sent for {task_id}. Waiting for client acknowledgment...")
    try:
        while True:
            client_msg = await websocket.receive_text()
            if _is_ack_message(client_msg):
                logger.info(f"Client acknowledged receipt for task {task_id}.")
                break
    except WebSocketDisconnect:
        logger.info(f"Client safely disconnected after reading terminal state for {task_id}.")


def _is_ack_message(raw_msg: str) -> bool:
    """Check if the incoming message is an acknowledgment signal."""
    if raw_msg.strip().upper() == ACK_MESSAGE:
        return True
    try:
        data = json.loads(raw_msg)
        return data.get("action") == ACK_MESSAGE
    except json.JSONDecodeError:
        return False


def _extract_state(raw_data: str) -> str | None:
    """Extract the state string from JSON payload if present."""
    try:
        return json.loads(raw_data).get("state")
    except json.JSONDecodeError:
        return None


async def _handle_cached_terminal_state(websocket: WebSocket, initial_state: str, task_id: str) -> bool:
    """Send cached state and terminate if already in a terminal state."""
    await websocket.send_text(initial_state)
    state = _extract_state(initial_state)

    if state in TERMINAL_STATES:
        logger.info(f"Task {task_id} already in terminal state ({state}). Awaiting client ACK.")
        await wait_for_client_ack(websocket, task_id)
        await websocket.close(code=1000, reason="Task finished and acknowledged")
        return True
    return False


async def _cleanup_redis(pubsub, redis_client, channel_name: str, task_id: str) -> None:
    """Safely unsubscribe and close Redis connections."""
    try:
        await pubsub.unsubscribe(channel_name)
        await pubsub.close()
        await redis_client.close()
    except Exception:
        logger.warning(
            f"Error during cleanup of Redis connection for task {task_id}",
            exc_info=True,
        )
    logger.info(f"Cleaned up Redis connection for task: {task_id}")


@ws_router.websocket("/ws/{task_id}")
async def websocket_route_status(websocket: WebSocket, task_id: str):
    await websocket.accept()

    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()

    channel_name = f"{ws_channel_prefix}:{task_id}"
    state_key = f"{ws_state_key_prefix}:{task_id}"

    # 1. Handle existing state from cache
    initial_state = await redis_client.get(state_key)
    if initial_state and await _handle_cached_terminal_state(websocket, initial_state, task_id):
        await redis_client.close()
        return

    # 2. Subscribe to real-time events
    await pubsub.subscribe(channel_name)
    logger.info(f"WebSocket subscribed to real-time events on: {channel_name}")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if not message or message.get("type") != "message":
                await asyncio.sleep(0.1)
                continue

            raw_data = message.get("data")
            if not raw_data:
                await asyncio.sleep(0.1)
                continue

            logger.info(f"Forwarding state to client ({task_id}): {raw_data}")
            await websocket.send_text(raw_data)

            state = _extract_state(raw_data)
            if state in TERMINAL_STATES:
                await wait_for_client_ack(websocket, task_id)
                await websocket.close(code=1000, reason=f"Task {state} acknowledged")
                break

            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        logger.info(f"Client disconnected from WebSocket: {task_id}")
    except asyncio.CancelledError:
        logger.info(f"WebSocket cancelled: {task_id}")
    except Exception as exc:
        logger.error(
            f"Unexpected error in WebSocket session for {task_id}: {exc}",
            exc_info=True,
        )
    finally:
        await _cleanup_redis(pubsub, redis_client, channel_name, task_id)
