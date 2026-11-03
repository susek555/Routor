import asyncio
import json
import logging
import time

import redis

from src.api.data.task_payload import TaskPayload
from src.api.data.task_state import TaskState
from src.database.database import get_single_dummy_message
from src.firebase_notification import send_push_notification
from src.generate_routes.worker_app import celery_app, redis_url

logger = logging.getLogger(__name__)






@celery_app.task(name="generate_routes.dummy_task")
def dummy_task(fcm_token: str, ip: str, dummy_message: str):
    print(f"Starting heavy task for user {ip}...")
    time.sleep(10)

    try:
        message_from_db = asyncio.run(get_single_dummy_message())
        print(f"Database communication successful. Retrieved: {message_from_db}")

    except Exception as e:
        print(f"CRITICAL ERROR: Failed to communicate with DB inside Celery: {str(e)}")
        raise e

    r = redis.Redis.from_url(redis_url)
    payload = {
        "event": "DUMMY_TASK_PERFORMED",
        "status": "success",
        "user_ip": ip,
        "message": "Message from worker through redis websocket.",
    }

    # REDIS
    print("Publishing notification to Redis channel...")
    r.publish("global_notifications", json.dumps(payload))

    # GOOGLE FIREBASE
    send_push_notification(
        fcm_token, "Task has been finished", "Messege through google firebase"
    )

    print("Task finished!")
    return {
        "status": "success",
        "user_ip": ip,
        "message_api": dummy_message,
        "message_database": message_from_db,
    }

@celery_app.task(bind=True, name="generate_routes.generate")
def generate_route_task(self, payload: TaskPayload):
    logger.info(f"Starting route generation task for user {payload.user_id}...")

def update_task_state(task_id: str, payload: TaskState, r: redis.Redis):
    data = payload.model_dump_json()
    state_key = f"routes:state:{task_id}"
    channel = f"routes:{task_id}"

    # TTL = 30 minutes
    r.set(state_key, data, ex=1800)

    # Inform active WebSocket clients about the state change
    r.publish(channel, data)
