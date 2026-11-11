from fastapi import FastAPI

from src.api.exceptions.exceptions_handler import setup_exception_handlers
from src.api.routes import routes_router
from src.api.routes_ws import ws_router

app = FastAPI(title="Routor API")
setup_exception_handlers(app)
app.include_router(routes_router)
app.include_router(ws_router)
