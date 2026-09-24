import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from backend.src.config import CORS_ORIGINS, MEDIA_DIR, READ_ONLY, REPO_ROOT
from backend.src.api.guards import ReadOnlyAPIMiddleware
from backend.src.api.routes.matches import router as matches_router
from backend.src.api.routes.comments import router as comments_router
from backend.src.services.pipeline.video_processor import VideoProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("veo_clone_app")

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

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

    # Startup: Ensure Fairfax Union match is registered if sample assets are present
    fairfax_id = "fairfax-union-20260920"
    from backend.src.storage.repository import match_repo
    if not match_repo.get_match(fairfax_id):
        fairfax_video = MEDIA_DIR / "fairfax_union_sample_30s.mp4"
        fairfax_calib = REPO_ROOT / "benchmarks" / "raw" / "fairfax_union_camera_alignment.veo"
        if fairfax_video.exists() and fairfax_calib.exists():
            import time
            from backend.src.domain.models.match import Match
            from backend.src.services.pipeline.pipeline_runner import MatchPipeline
            m = Match(
                id=fairfax_id,
                title="Arlington SA U16B ECNL (26-27) vs. Fairfax Union",
                home_team="Arlington SA U16B ECNL",
                away_team="Fairfax Union",
                home_score=3,
                away_score=0,
                date="Sep 20, 2026",
                duration_seconds=30.0,
                status="ready",
                processing_step="Complete",
                processing_progress=100.0,
                video_url="/media/fairfax_union_sample_30s.mp4",
                panoramic_url="/media/fairfax_union_sample_30s.mp4",
                thumbnail_url="/media/demo_thumb.jpg",
                views_count=32,
                journal_notes="Dominant 3-0 clean sheet. Fluid central progression and clinical inside-box finishing.",
                analysis_mode="ml",
                analysis_confidence="medium",
                created_at=time.time(),
            )
            match_repo.save_match(m)
            try:
                pipeline = MatchPipeline(match_id=fairfax_id, mode="ml", calib_file=fairfax_calib, repo=match_repo)
                pipeline.run()
            except Exception as e:
                logger.warning(f"Could not run MatchPipeline for Fairfax Union: {e}")

    # Startup: Ensure Baltimore Armor match is registered if sample assets are present
    baltimore_id = "baltimore-armor-20260906"
    if not match_repo.get_match(baltimore_id):
        baltimore_video = MEDIA_DIR / "baltimore_armor_sample_30s.mp4"
        baltimore_calib = REPO_ROOT / "benchmarks" / "raw" / "baltimore_armor_camera_alignment.veo"
        if baltimore_video.exists() and baltimore_calib.exists():
            import time
            from backend.src.domain.models.match import Match
            from backend.src.services.pipeline.pipeline_runner import MatchPipeline
            m_balt = Match(
                id=baltimore_id,
                title="Arlington SA U16B ECNL (26-27) vs. Baltimore Armor",
                home_team="Arlington SA U16B ECNL",
                away_team="Baltimore Armor",
                home_score=3,
                away_score=0,
                date="Sep 6, 2026",
                duration_seconds=30.0,
                status="ready",
                processing_step="Complete",
                processing_progress=100.0,
                video_url="/media/baltimore_armor_sample_30s.mp4",
                panoramic_url="/media/baltimore_armor_sample_30s.mp4",
                thumbnail_url="/media/demo_thumb.jpg",
                views_count=28,
                journal_notes="Tactical 3-0 victory against Baltimore Armor. High pressing and sustained defensive discipline.",
                analysis_mode="ml",
                analysis_confidence="medium",
                created_at=time.time(),
            )
            match_repo.save_match(m_balt)
            try:
                pipeline = MatchPipeline(match_id=baltimore_id, mode="ml", calib_file=baltimore_calib, repo=match_repo)
                pipeline.run()
            except Exception as e:
                logger.warning(f"Could not run MatchPipeline for Baltimore Armor: {e}")

    yield
    logger.info("Shutting down Veo Analysis API.")

app = FastAPI(
    title="Veo Video Analysis Replication API",
    description="Video analysis, AI player tracking, event detection, and coaching studio mirroring Veo.app",
    version="1.0.0",
    lifespan=lifespan
)

# Reject all client-side API mutations when configured as read-only.
app.add_middleware(ReadOnlyAPIMiddleware, enabled=READ_ONLY)

# Security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Enable CORS for local dev and frontend without wildcard + credentials collision
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded & generated media (videos, thumbnails, clips)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

# Include API routes
app.include_router(matches_router)
app.include_router(comments_router)

@app.get("/api/capabilities")
def get_capabilities():
    return {
        "read_only": READ_ONLY,
        "allow_uploads": not READ_ONLY,
        "supported_analysis_modes": ["demo", "heuristic", "ml"],
        "execution_targets": [
            {
                "id": "local",
                "name": "Local Engine",
                "status": "online",
                "badge": "Active",
                "description": "Hermetic in-process CPU/GPU ML pipeline"
            },
            {
                "id": "gpu_box",
                "name": "Remote GPU-Box (H100)",
                "status": "auth_required",
                "badge": "Tailscale Auth Required",
                "auth_url": "https://login.tailscale.com/a/lb70eee53af031",
                "description": "Tailscale cluster host (root@gpu-box)"
            }
        ],
        "default_target": "local"
    }

@app.get("/api/pipeline/execution-targets")
def get_pipeline_execution_targets():
    """List available pipeline execution targets (Local hermetic engine vs remote GPU-box)."""
    return {
        "targets": [
            {
                "id": "local",
                "name": "Local Engine",
                "status": "online",
                "badge": "Active",
                "description": "Hermetic in-process CPU/GPU ML pipeline"
            },
            {
                "id": "gpu_box",
                "name": "Remote GPU-Box (H100)",
                "status": "auth_required",
                "badge": "Tailscale Auth Required",
                "auth_url": "https://login.tailscale.com/a/lb70eee53af031",
                "description": "Tailscale cluster host (root@gpu-box)"
            }
        ],
        "default": "local"
    }

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
