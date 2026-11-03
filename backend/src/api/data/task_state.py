from enum import Enum

from pydantic import BaseModel


class TaskStateEnum(Enum):
    LOADING_GRAPH = "LOADING_GRAPH"
    SIMPLIFYING_GRAPH = "SIMPLIFYING_GRAPH"
    GENERATING_ROUTE = "GENERATING_ROUTE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FailedTaskStatePayload(BaseModel):
    error_message: str


class ProgressTaskStatePayload(BaseModel):
    done: int
    total: int


# Zamiast: Union[FailedTaskStatePayload, ProgressTaskStatePayload, None]
type TaskPayloadType = FailedTaskStatePayload | ProgressTaskStatePayload | None


class TaskState(BaseModel):
    state: TaskStateEnum
    payload: TaskPayloadType = None
