import os

from celery import Celery

redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
celery_app = Celery("routor_tasks", broker=redis_url, backend=redis_url)

celery_app.conf.update(
    imports=["src.generate_routes.task"],
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
