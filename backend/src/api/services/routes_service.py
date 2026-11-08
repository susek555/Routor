# services/route_dispatcher.py
import logging

from kombu.exceptions import OperationalError

from src.api.data.task_payload import TaskPayload
from src.api.exceptions.exceptions import ServiceUnavailableError
from src.generate_routes.task import generate_route_task

logger = logging.getLogger(__name__)


class RouteService:
    @staticmethod
    def dispatch(payload: TaskPayload) -> str:
        logger.info(f"Scheduling route generation for user {payload.user_id}...")
        try:
            task = generate_route_task.delay(payload.model_dump(mode="json"))
            logger.info(f"Route task {task.id} scheduled for user {payload.user_id}.")
            return task.id
        except OperationalError as exc:
            logger.error(f"Celery broker unavailable: {exc}")
            raise ServiceUnavailableError("Message broker is unreachable.") from exc
