import uuid

from pydantic import BaseModel

from src.generate_routes.data.geo_point import GeoPoint


class TaskPayload(BaseModel):
    user_id: uuid.UUID | None = None
    fcm_token: str
    center: GeoPoint
    target_distance: float
