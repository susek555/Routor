import os

from celery import Celery

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://routor_redis:6379/0")
celery_app = Celery("routor_tasks", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    imports=["src.generate_routes.task"],
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
