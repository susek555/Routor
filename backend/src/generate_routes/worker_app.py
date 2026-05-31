import os
import time

from celery import Celery

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
celery_app = Celery("routor_tasks", broker=broker_url)

@celery_app.task
def heavy_computation_task(user_id: int, data_payload: dict):
    print(f"Starting heavy task for user {user_id}...")
    time.sleep(10)

    #TODO

    print("Task finished!")
    return {"status": "success", "user_id": user_id}
