from pydantic import BaseModel
from src.generate_routes.data.geo_point import GeoPoint


class TaskPayload(BaseModel):
    fcm_token: str
    user_id: str
    center: GeoPoint
    target_distance: float
