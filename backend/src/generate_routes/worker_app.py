import os

from celery import Celery

REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://routor_redis:6379/0")
celery_app = Celery("routor_tasks", broker=REDIS_URL, backend=REDIS_URL)
ws_channel_prefix = "routes"  # Prefix for Redis channels used for WebSocket communication
ws_state_key_prefix = "routes:state"  # Prefix for Redis keys used to store task states

celery_app.conf.update(
    imports=["src.generate_routes.task"],
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)
