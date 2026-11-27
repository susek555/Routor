from fastapi import APIRouter, status

from src.api.data.auth import AuthRequest, LogoutRequest, TokenResponse
from src.api.services.auth_service import AuthService
from src.database.database import DbSession

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: AuthRequest,
    db: DbSession,
) -> TokenResponse:
    """Registers a new user and returns an authentication token."""
    raw_token, expires_at = await AuthService.register_user(
        session=db,
        username=payload.username,
        password=payload.password,
    )
    return TokenResponse(token=raw_token, expires_at=expires_at)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: AuthRequest,
    db: DbSession,
) -> TokenResponse:
    """Authenticates a user and returns a new authentication token."""
    raw_token, expires_at = await AuthService.login_user(
        session=db,
        username=payload.username,
        password=payload.password,
    )
    return TokenResponse(token=raw_token, expires_at=expires_at)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    db: DbSession,
) -> None:
    """Revokes the provided authentication token."""
    await AuthService.logout_user(session=db, raw_token=payload.token)
