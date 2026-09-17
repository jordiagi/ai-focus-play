import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.src.api.routes.matches import router as matches_router
from backend.src.services.pipeline.video_processor import VideoProcessor, MEDIA_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("veo_clone_app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure demo video and thumbnail exist
    demo_video = MEDIA_DIR / "demo_match.mp4"
    demo_thumb = MEDIA_DIR / "demo_thumb.jpg"
    if not demo_video.exists():
        logger.info("Generating default demo soccer video fixture...")
        VideoProcessor.generate_demo_soccer_video(demo_video, duration=90)
    if not demo_thumb.exists() and demo_video.exists():
        logger.info("Generating default demo thumbnail...")
        VideoProcessor.extract_thumbnail(demo_video, demo_thumb, time_sec=5.0)

    yield
    logger.info("Shutting down Veo Analysis API.")

app = FastAPI(
    title="Veo Video Analysis Replication API",
    description="Video analysis, AI player tracking, event detection, and coaching studio mirroring Veo.app",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local dev and frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded & generated media (videos, thumbnails, clips)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# Include API routes
app.include_router(matches_router)

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "Veo Video Analysis Engine",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.src.app.main:app", host="0.0.0.0", port=8000, reload=True)
