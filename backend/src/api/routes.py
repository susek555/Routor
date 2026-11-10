import json
import logging
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.data.route_generation_response import RouteGenerationResponse
from src.api.data.task_payload import TaskPayload
from src.api.data.task_state import TaskStateEnum
from src.api.services.routes_service import RouteService
from src.app import REDIS_URL, app
from src.database.database import get_db
from src.database.query.route import get_route_variants_by_task_id
from src.database.schemas.route import RouteVariantResponse, TaskRouteVariantsResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/routes", tags=["Routes"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RouteGenerationResponse,
)
async def generate_route(payload: TaskPayload) -> RouteGenerationResponse:
    task_id = RouteService.dispatch(payload)
    return RouteGenerationResponse(task_id=task_id)


# @app.post("/dummy-task")
# async def dummy_task_endpoint(payload: TaskPayload, request: Request):
#     task = dummy_task.delay(
#         payload.fcm_token, request.client.host, "Message from api."
#     )

#     return {
#         "status": "Accepted",
#         "message": "Dummy task started in the background.",
#         "task_id": task.id,
#     }


async def handle_task_finished_state(message: dict, websocket: WebSocket) -> bool:
    """Check if the task reached a terminal state and close the WebSocket if needed.

    Returns:
        bool: True if connection was closed, False otherwise.
    """
    current_state = message.get("state")
    payload = message.get("payload") or {}

    if current_state == TaskStateEnum.COMPLETED.value:
        # 1000: Standard Normal Closure
        await websocket.close(code=1000, reason="Task completed")
        return True

    if current_state == TaskStateEnum.FAILED.value:
        error_msg = payload.get("error_message") or payload.get("error", "Task failed")
        # 4001: Custom Application Error code
        await websocket.close(code=4001, reason=error_msg)
        return True

    return False


@app.websocket("/ws/routes/{task_id}")
async def websocket_route_progress(websocket: WebSocket, task_id: str) -> None:
    # Accept the incoming WebSocket connection from the mobile app
    await websocket.accept()

    r = aioredis.from_url(REDIS_URL)
    state_key = f"routes:state:{task_id}"
    channel_name = f"routes:{task_id}"

    try:
        # Step 1: Check the latest cached state in Redis before subscribing
        raw_state = await r.get(state_key)

        if raw_state:
            state_data = json.loads(raw_state.decode("utf-8"))

            # Push the most recent state snapshot directly to the client
            await websocket.send_text(raw_state.decode("utf-8"))

            # If task already reached a terminal state, terminate early
            if await handle_task_finished_state(state_data, websocket):
                return

        # Step 2: The task is still running; subscribe to real-time events via Redis Pub/Sub
        pubsub = r.pubsub()
        await pubsub.subscribe(channel_name)

        # Listen for real-time progress updates published by the Celery worker
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            raw_msg = message["data"].decode("utf-8")
            state_data = json.loads(raw_msg)

            # Stream the update to the client
            await websocket.send_text(raw_msg)

            # Close and break the loop if task finished
            if await handle_task_finished_state(state_data, websocket):
                break

    except WebSocketDisconnect:
        # Handled when the client disconnects gracefully or minimizes the app
        pass
    finally:
        # Clean up Redis Pub/Sub subscription and connection pool
        if pubsub is not None:
            await pubsub.unsubscribe(channel_name)
            await pubsub.aclose()
        await r.aclose()


@router.get(
    "/{task_id}",
    response_model=TaskRouteVariantsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_task_routes(
    task_id: str,
    db: DbSession,
):
    """Retrieves all generated route variants for a given task."""
    variants = await get_route_variants_by_task_id(db, task_id)


    return TaskRouteVariantsResponse(
        task_id=task_id,
        total_variants=len(variants),
        variants=[RouteVariantResponse.model_validate(v) for v in variants],
    )
