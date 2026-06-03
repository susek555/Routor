import asyncio
import json
import os

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect

from src.database.database import get_dummies
from src.generate_routes.task import dummy_task

app = FastAPI(title="Routor API")

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://routor_redis:6379/0")


@app.get("/dummy")
def get_dummy():
    return {"message": "Dummy"}


@app.get("/healthcheck-db")
async def check_db_connection():
    try:
        rows = await get_dummies()

        return {
            "status": "ok",
            "database": "connected",
            "records_count": len(rows),
            "data": rows,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error connecting to database: {str(e)}"
        ) from e


@app.post("/dummy-task")
async def dummy_task_endpoint(request: Request):
    task = dummy_task.delay(request.client.host, "Message from api.")

    return {
        "status": "Accepted",
        "message": "Dummy task started in the background.",
        "task_id": task.id,
    }


@app.websocket("/ws/notifications")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print(" [WS] Client connected via WebSocket")

    redis_client = aioredis.from_url(REDIS_URL)
    pubsub = redis_client.pubsub()

    await pubsub.subscribe("global_notifications")

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=1.0
            )

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
