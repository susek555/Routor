# app/exception_handlers.py
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.api.exceptions.exceptions import ServiceUnavailableError


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceUnavailableError)
    async def service_unavailable_handler(request: Request, exc: ServiceUnavailableError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": exc.message},
        )
