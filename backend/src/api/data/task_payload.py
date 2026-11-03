from pydantic import BaseModel
from src.database.geo_point import GeoPoint


class TaskPayload(BaseModel):
    fcm_token: str
    user_id: str
    center: GeoPoint
    target_distance: float
