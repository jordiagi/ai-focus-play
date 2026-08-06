from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware.error_handling import register_error_handlers
from src.api.routes.projects import router as projects_router
from src.api.routes.jobs import router as jobs_router
from src.api.routes.frames import router as frames_router
from src.api.routes.clicks import router as clicks_router
from src.api.routes.sources import router as sources_router
from src.api.routes.exports import router as exports_router
from src.app.logging import configure_logging
from src.app.dependencies import job_service


configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    job_service().start_next()
    yield


app = FastAPI(title="AI Focus Play", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)
app.include_router(projects_router)
app.include_router(sources_router)
app.include_router(jobs_router)
app.include_router(frames_router)
app.include_router(clicks_router)
app.include_router(exports_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "AI Focus Play API",
        "status": "ok",
        "docs": "/docs",
        "frontend": "http://localhost:5173",
    }
