import asyncio
import json
import time

import redis

from src.database.database import get_single_dummy_message
from src.firebase_notification import send_push_notification
from src.generate_routes.worker_app import celery_app, redis_url


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
