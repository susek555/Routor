import datetime

from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class TokenResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_at: datetime


class LogoutRequest(BaseModel):
    token: str
