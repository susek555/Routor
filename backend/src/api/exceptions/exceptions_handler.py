from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.api.exceptions.exceptions import (
    GraphGenerationError,
    InvalidCredentialsError,
    InvalidTokenError,
    NoRouteVariantsFoundError,
    ServiceUnavailableError,
    UsernameAlreadyExistsError,
)


def setup_exception_handlers(app: FastAPI) -> None:
    """Registers custom exception handlers for the FastAPI application."""

    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_handler(request: Request, exc: ServiceUnavailableError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": exc.message},
        )

    @app.exception_handler(GraphGenerationError)
    async def graph_generation_handler(request: Request, exc: GraphGenerationError):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": exc.message},
        )

    @app.exception_handler(NoRouteVariantsFoundError)
    async def no_route_variants_found_handler(request: Request, exc: NoRouteVariantsFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message},
        )

    @app.exception_handler(UsernameAlreadyExistsError)
    async def username_already_exists_handler(request: Request, exc: UsernameAlreadyExistsError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.message},
        )

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": exc.message},
        )

    @app.exception_handler(InvalidTokenError)
    async def invalid_token_handler(request: Request, exc: InvalidTokenError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": exc.message},
        )
