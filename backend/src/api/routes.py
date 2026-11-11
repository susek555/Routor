import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.data.route_generation_response import RouteGenerationResponse
from src.api.data.task_payload import TaskPayload
from src.api.services.routes_service import RouteService
from src.database.database import get_db
from src.database.query.route import get_route_variants_by_task_id
from src.database.schemas.route import RouteVariantResponse, TaskRouteVariantsResponse

logger = logging.getLogger(__name__)
routes_router = APIRouter(prefix="/routes", tags=["Routes"])
DbSession = Annotated[AsyncSession, Depends(get_db)]


@routes_router.post(
    "/generate",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RouteGenerationResponse,
)
async def generate_route(payload: TaskPayload) -> RouteGenerationResponse:
    task_id = RouteService.dispatch(payload)
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
    """Retrieves all generated route variants for a given task."""
    variants = await get_route_variants_by_task_id(db, task_id)

    return TaskRouteVariantsResponse(
        task_id=task_id,
        total_variants=len(variants),
        variants=[RouteVariantResponse.model_validate(v) for v in variants],
    )
