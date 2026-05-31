import asyncio
import time

from src.database.database import get_single_dummy_message
from src.generate_routes.worker_app import celery_app


@celery_app.task(name="generate_routes.dummy_task")
def dummy_task(ip: str, dummy_message: str):
    print(f"Starting heavy task for user {ip}...")
    time.sleep(10)

    try:
        message_from_db = asyncio.run(get_single_dummy_message())
        print(f"Database communication successful. Retrieved: {message_from_db}")

    except Exception as e:
        print(f"CRITICAL ERROR: Failed to communicate with DB inside Celery: {str(e)}")
        raise e

    print("Task finished!")
    return {
        "status": "success",
        "user_ip": ip,
        "message_api": dummy_message,
        "message_database": message_from_db,
    }
