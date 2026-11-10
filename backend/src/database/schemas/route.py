from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class RouteVariantResponse(BaseModel):
    id: UUID
    variant_index: int
    distance_meters: int
    fitness_score: float
    geojson: dict[str, Any]
    created_at: datetime
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskRouteVariantsResponse(BaseModel):
    task_id: str
    total_variants: int
    variants: list[RouteVariantResponse]
