import logging
import uuid

from kombu.exceptions import OperationalError

from src.api.data.task_payload import TaskPayload
from src.api.exceptions.exceptions import ServiceUnavailableError
from src.generate_routes.task import generate_route_task

logger = logging.getLogger(__name__)


class RouteService:
    """Dispatches route generation jobs to the Celery worker."""

    @staticmethod
    def dispatch(payload: TaskPayload, user_id: uuid.UUID | str) -> str:
        """Schedules route generation with user context included in the task payload."""
        logger.info(f"Scheduling route generation for user {user_id}...")
        task_data = payload.model_dump(mode="json")
        task_data["user_id"] = str(user_id)

        try:
            task = generate_route_task.delay(task_data)
            logger.info(f"Route task {task.id} scheduled for user {user_id}.")
            return task.id
        except OperationalError as exc:
            logger.error(f"Celery broker unavailable: {exc}")
            raise ServiceUnavailableError("Message broker is unreachable.") from exc
