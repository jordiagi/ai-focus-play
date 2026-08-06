from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.app.errors import AppError
from src.app.logging import log_event


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        log_event("app_error", message=exc.message, status_code=exc.status_code)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})

