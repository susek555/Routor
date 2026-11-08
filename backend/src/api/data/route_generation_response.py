from pydantic import BaseModel


class RouteGenerationResponse(BaseModel):
    task_id: str
