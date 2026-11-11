import asyncio
import json

import redis.asyncio as aioredis
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.api.exceptions.exceptions_handler import setup_exception_handlers
from src.generate_routes.worker_app import REDIS_URL

app = FastAPI(title="Routor API")
setup_exception_handlers(app)


class TaskPayload(BaseModel):
    fcm_token: str


@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(" [WS] Client connected via WebSocket")

    redis_client = aioredis.from_url(REDIS_URL)
    pubsub = redis_client.pubsub()

    await pubsub.subscribe("global_notifications")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)

            if message:
                raw_data = message["data"]
                data = json.loads(raw_data.decode("utf-8"))

                print(f" [WS] Got data from Redis, sending to client: {data}")

                await websocket.send_json(data)

            await asyncio.sleep(0.1)

    except WebSocketDisconnect:
        print(" [WS] Client disconnected")
    finally:
        await pubsub.unsubscribe("global_notifications")
        await redis_client.close()
