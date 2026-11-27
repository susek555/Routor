import logging

from fastapi import APIRouter, status

from src.api.data.route_generation_response import RouteGenerationResponse
from src.api.data.task_payload import TaskPayload
from src.api.services.auth_service import CurrentUser
from src.api.services.routes_service import RouteService
from src.database.database import DbSession
from src.database.query.route import get_route_variants_by_task_id
from src.database.schemas.route import RouteVariantResponse, TaskRouteVariantsResponse

logger = logging.getLogger(__name__)
routes_router = APIRouter(
    prefix="/routes",
    tags=["Routes"],
    dependencies=[CurrentUser]  # Ensure the user is authenticated
    )


@routes_router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RouteGenerationResponse,
)
async def generate_route(payload: TaskPayload, current_user: CurrentUser) -> RouteGenerationResponse:
    task_id = RouteService.dispatch(payload, user_id=current_user.id)
    return RouteGenerationResponse(task_id=task_id)


@routes_router.get(
    "/{task_id}",
    response_model=TaskRouteVariantsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_task_routes(
    task_id: str,
    db: DbSession,
):
    """Retrieves all generated route variants for a given task for an authenticated user."""
    variants = await get_route_variants_by_task_id(db, task_id)

    return TaskRouteVariantsResponse(
        task_id=task_id,
        total_variants=len(variants),
        variants=[RouteVariantResponse.model_validate(v) for v in variants],
    )
