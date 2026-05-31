import time

from src.generate_routes.worker_app import celery_app


@celery_app.task(name="generate_routes.dummy_task")
def dummy_task(ip: str, dummy_message: str):
    print(f"Starting heavy task for user {ip}...")
    time.sleep(10)

    # TODO

    print("Task finished!")
    return {"status": "success", "user_ip": ip, "message": dummy_message}
