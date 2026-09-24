import os
import json
import tempfile
import zipfile
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import anyio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.src.config import MAX_UPLOAD_BYTES, READ_ONLY, MEDIA_DIR
from backend.src.domain.models.match import (
    Match, Highlight, Event, Drawing, RadarFrame, AnalyticsData, PlayerRoster
)
from backend.src.storage.repository import match_repo
from backend.src.services.pipeline.video_processor import VideoProcessor
from backend.src.services.pipeline.cv_engine import cv_engine

logger = logging.getLogger("api_matches")
router = APIRouter(prefix="/api/matches", tags=["matches"])

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}

class CreateHighlightRequest(BaseModel):
    title: str
    event_type: str
    start_time: float
    end_time: float
    period: int = 1
    team: str = "home"
    player_jersey: Optional[str] = None
    player_name: Optional[str] = None
    tags: List[str] = []

class CreateDrawingRequest(BaseModel):
    timestamp: float
    tool_type: str
    color: str = "#00E676"
    coordinates: List[Dict[str, float]]
    text_label: Optional[str] = None

class UpdateJournalRequest(BaseModel):
    journal_notes: str

def process_uploaded_video_task(match_id: str, video_path: Path, job_id: Optional[str] = None):
    """Background worker executing computer vision pipeline."""
    match = match_repo.get_match(match_id)
    if not match:
        return

    try:
        if job_id:
            match_repo.update_job(job_id, status="running", progress=10.0, step="Extracting thumbnail and metadata...")

        # 1. Generate thumbnail
        thumb_path = MEDIA_DIR / f"{match_id}_thumb.jpg"
        if VideoProcessor.extract_thumbnail(video_path, thumb_path, time_sec=2.0):
            match.thumbnail_url = f"/media/{thumb_path.name}"
            match_repo.save_match(match)

        # 2. Extract metadata
        meta = VideoProcessor.get_video_metadata(video_path)
        match.duration_seconds = meta.get("duration", 90.0)

        # 3. Run CV Analysis Engine
        if job_id:
            match_repo.update_job(job_id, progress=30.0, step="Running player tracking and field homography...")

        def on_cv_progress(p: float, step_name: str):
            match.processing_progress = round(20.0 + p * 0.7, 1)
            match.processing_step = step_name
            match_repo.save_match(match)
            if job_id:
                match_repo.update_job(job_id, progress=match.processing_progress, step=step_name)

        radar_frames, events, highlights, analytics = cv_engine.process_video(
            video_path=video_path,
            progress_callback=on_cv_progress
        )

        for e in events:
            e.match_id = match_id
        for h in highlights:
            h.match_id = match_id

        # 4. Save results (internal=True bypasses client-side read-only restriction)
        match_repo.save_radar_frames(match_id, radar_frames)
        match_repo.set_events(match_id, events)
        for h in highlights:
            clip_path = MEDIA_DIR / f"clip_{h.id}.mp4"
            if VideoProcessor.cut_clip(video_path, clip_path, h.start_time, h.end_time):
                h.clip_url = f"/media/{clip_path.name}"
            # Internal write allowed for automated pipeline
            match_repo.add_highlight(h, internal=True)

        match_repo.set_analytics(match_id, analytics)

        # Honest label: report the mode the engine actually ran (P-WP2-4). If the
        # engine tells us nothing -- e.g. it silently fell back to synthetic
        # tracking, or hasn't been wired up to report meta yet -- we must not
        # claim more than "demo"/"low".
        run_meta = getattr(cv_engine, "last_run_meta", {}) or {}
        mode = run_meta.get("mode", "demo")
        confidence = run_meta.get("confidence", "low")
        if mode not in ("demo", "heuristic", "ml"):
            mode = "demo"
        if confidence not in ("low", "medium", "high"):
            confidence = "low"

        match.status = "ready"
        match.processing_step = "Analysis Complete"
        match.processing_progress = 100.0
        match.analysis_mode = mode
        match.analysis_confidence = confidence
        match_repo.save_match(match)

        if job_id:
            match_repo.update_job(job_id, status="completed", progress=100.0, step="Analysis complete")
        logger.info(f"Successfully processed match {match_id}")

    except Exception as e:
        logger.error(f"Error in video processing task for {match_id}: {e}", exc_info=True)
        match.status = "error"
        match.error_message = str(e)
        match_repo.save_match(match)
        if job_id:
            match_repo.update_job(job_id, status="failed", error=str(e), step="Failed")

@router.get("", response_model=List[Match])
def list_matches():
    return match_repo.list_matches()

@router.get("/{match_id}", response_model=Match)
def get_match(match_id: str):
    match = match_repo.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match

@router.delete("/{match_id}")
def delete_match(match_id: str):
    match_repo.delete_match(match_id)
    return {"status": "success", "message": f"Match {match_id} deleted"}

@router.post("/upload", response_model=Match)
async def upload_match(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    home_team: str = Form("Home Team"),
    away_team: str = Form("Away Team"),
    date: str = Form("Today"),
    title: Optional[str] = Form(None)
):
    if not title:
        title = f"{home_team} vs. {away_team}"

    # Validate video extension (P2-3)
    filename = file.filename or "match.mp4"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}"
        )

    import uuid
    match_id = str(uuid.uuid4())
    dest_path = MEDIA_DIR / f"{match_id}{ext}"

    # Asynchronous chunked streaming upload with size validation (P2-3)
    total_bytes = 0
    try:
        async with await anyio.open_file(dest_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds maximum upload size limit of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
                    )
                await f.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to stream upload: {e}")

    # Probe file to ensure it is valid video before creating record
    try:
        meta = VideoProcessor.get_video_metadata(dest_path)
        duration = meta.get("duration", 90.0)
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Uploaded file is corrupt or unreadable: {e}")

    match = Match(
        id=match_id,
        title=title,
        home_team=home_team,
        away_team=away_team,
        date=date,
        duration_seconds=duration,
        video_url=f"/media/{dest_path.name}",
        panoramic_url=f"/media/{dest_path.name}",
        status="processing",
        processing_step="Queued for analysis...",
        processing_progress=5.0,
        analysis_mode="demo",
        analysis_confidence="low",
        views_count=1
    )
    match_repo.save_match(match)

    # Create job entry (P2-4)
    job_id = match_repo.create_job(match_id=match_id, kind="cv_analysis")

    background_tasks.add_task(process_uploaded_video_task, match_id, dest_path, job_id)
    return match

@router.get("/{match_id}/progress")
def get_match_progress(match_id: str):
    """Returns real-time processing status and progress for a match."""
    match = match_repo.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    job = match_repo.get_job_by_match(match_id)
    return {
        "match_id": match_id,
        "status": match.status,
        "step": match.processing_step,
        "progress": match.processing_progress,
        "error": match.error_message,
        "job_id": job["id"] if job else None,
        "job_status": job["status"] if job else None
    }

@router.get("/{match_id}/radar", response_model=List[RadarFrame])
def get_radar_frames(
    match_id: str,
    time: Optional[float] = Query(None, description="Optional timestamp for single frame")
):
    frames = match_repo.get_radar_frames(match_id)
    if time is not None and frames:
        closest = min(frames, key=lambda f: abs(f.timestamp - time))
        return [closest]
    return frames

@router.get("/{match_id}/radar/window", response_model=List[RadarFrame])
def get_radar_window(
    match_id: str,
    start: float = Query(0.0, ge=0.0, description="Start time in seconds"),
    end: float = Query(90.0, ge=0.0, description="End time in seconds")
):
    """Chunked radar frame pagination (P2-1)."""
    return match_repo.get_radar_frames_window(match_id, start_time=start, end_time=end)

@router.get("/{match_id}/radar/meta")
def get_radar_meta(match_id: str):
    """Returns radar metadata (frame count, duration, fps) (P2-1)."""
    return match_repo.get_radar_meta(match_id)

@router.get("/{match_id}/analytics", response_model=AnalyticsData)
def get_analytics(match_id: str):
    analytics = match_repo.get_analytics(match_id)
    if not analytics:
        raise HTTPException(status_code=404, detail="Analytics not found for match")
    return analytics

@router.get("/{match_id}/benchmark")
def get_benchmark_comparison(match_id: str):
    """Compare match analytics against live Veo ground-truth benchmark."""
    match = match_repo.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    analytics = match_repo.get_analytics(match_id)
    if not analytics:
        raise HTTPException(status_code=404, detail="Analytics not found for match")
    try:
        from backend.src.services.pipeline.stats_benchmark import compare_stats_table, load_live_veo_benchmark
        gt_raw = load_live_veo_benchmark(f"{match.id} {match.title}")
        comparison = compare_stats_table(
            analytics.home_stats.model_dump(),
            analytics.away_stats.model_dump(),
            analytics.unavailable,
            gt_benchmark=gt_raw,
        )
        return {
            "match_id": match_id,
            "benchmark_match": gt_raw["match"],
            "comparison": comparison,
            "live_ground_truth": gt_raw
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Benchmark error: {str(e)}")

@router.post("/{match_id}/teams/swap")
def swap_teams(match_id: str):
    """Swap home and away team assignments across events, highlights, radar frames, and stats (P1-2)."""
    match = match_repo.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    match_repo.swap_teams(match_id)
    return {"status": "success", "message": "Teams successfully swapped"}

@router.get("/{match_id}/highlights", response_model=List[Highlight])
def get_highlights(match_id: str):
    return match_repo.get_highlights(match_id)

@router.post("/{match_id}/highlights", response_model=Highlight)
def create_highlight(match_id: str, req: CreateHighlightRequest):
    if READ_ONLY:
        raise HTTPException(status_code=403, detail="Read-only mode: Creating or writing new clips is disabled.")
    h = Highlight(
        match_id=match_id,
        title=req.title,
        event_type=req.event_type,
        start_time=req.start_time,
        end_time=req.end_time,
        period=req.period,
        team=req.team,
        player_jersey=req.player_jersey,
        player_name=req.player_name,
        tags=req.tags,
        is_ai_detected=False
    )
    return match_repo.add_highlight(h, internal=False)

@router.delete("/{match_id}/highlights/{highlight_id}")
def delete_highlight(match_id: str, highlight_id: str):
    if READ_ONLY:
        raise HTTPException(status_code=403, detail="Read-only mode: Deleting clips is disabled.")
    match_repo.delete_highlight(match_id, highlight_id, internal=False)
    return {"status": "success"}

def _iter_zip_file_and_cleanup(path: Path, chunk_size: int = 1024 * 1024):
    """Streams a file from disk in bounded-size chunks, deleting it once fully sent
    (or on error) so no request ever holds the whole archive in memory."""
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    finally:
        path.unlink(missing_ok=True)


@router.get("/{match_id}/highlights/export")
def export_highlights_zip(match_id: str):
    """Streams a zip archive of all cut highlight clips (P3-1). Builds the archive
    on disk (never in an in-memory buffer) and never substitutes a different file
    for a highlight whose clip is missing -- it is omitted and recorded in a
    manifest entry instead (defect 6)."""
    match = match_repo.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    highlights = match_repo.get_highlights(match_id)
    if not highlights:
        raise HTTPException(status_code=404, detail="No highlights to export")

    tmp = tempfile.NamedTemporaryFile(prefix="highlights_export_", suffix=".zip", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        manifest = []
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for idx, h in enumerate(highlights, 1):
                clip_file = None
                if h.clip_url and h.clip_url.startswith("/media/"):
                    candidate = MEDIA_DIR / h.clip_url.replace("/media/", "")
                    if candidate.exists():
                        clip_file = candidate

                if clip_file is not None:
                    safe_name = f"{idx:02d}_{h.event_type}_{h.title.replace(' ', '_')}.mp4"
                    zip_file.write(clip_file, arcname=safe_name)
                    manifest.append({
                        "highlight_id": h.id, "title": h.title, "file": safe_name,
                        "status": "included"
                    })
                else:
                    manifest.append({
                        "highlight_id": h.id, "title": h.title, "file": None,
                        "status": "omitted", "reason": "clip not available"
                    })
            zip_file.writestr("manifest.json", json.dumps(manifest, indent=2))
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    filename = f"{match.home_team}_vs_{match.away_team}_highlights.zip".replace(" ", "_")
    return StreamingResponse(
        _iter_zip_file_and_cleanup(tmp_path),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.get("/{match_id}/export/zip", include_in_schema=False)
def export_highlights_zip_alias(match_id: str):
    """Direct alias for /{match_id}/highlights/export."""
    return export_highlights_zip(match_id)

@router.get("/{match_id}/events", response_model=List[Event])
def get_events(match_id: str):
    return match_repo.get_events(match_id)

@router.get("/{match_id}/player-moments")
def get_player_moments(match_id: str, jersey: Optional[str] = Query(None)):
    """Returns moments, events, and highlights linked to a specific player jersey number."""
    highlights = match_repo.get_highlights(match_id)
    events = match_repo.get_events(match_id)

    if jersey:
        highlights = [h for h in highlights if h.player_jersey == jersey]
        events = [e for e in events if e.player_jersey == jersey]

    return {
        "jersey": jersey,
        "highlights_count": len(highlights),
        "highlights": highlights,
        "events": events
    }

@router.get("/{match_id}/drawings", response_model=List[Drawing])
def get_drawings(
    match_id: str,
    time: Optional[float] = Query(None, description="Filter drawings within 1 second of timestamp")
):
    drawings = match_repo.get_drawings(match_id)
    if time is not None:
        drawings = [d for d in drawings if abs(d.timestamp - time) <= 1.0]
    return drawings

@router.post("/{match_id}/drawings", response_model=Drawing)
def create_drawing(match_id: str, req: CreateDrawingRequest):
    d = Drawing(
        match_id=match_id,
        timestamp=req.timestamp,
        tool_type=req.tool_type,
        color=req.color,
        coordinates=req.coordinates,
        text_label=req.text_label
    )
    match_repo.add_drawing(d)
    return d

@router.delete("/{match_id}/drawings/{drawing_id}")
def delete_drawing(match_id: str, drawing_id: str):
    match_repo.delete_drawing(match_id, drawing_id)
    return {"status": "success"}

@router.delete("/{match_id}/drawings")
def clear_drawings(match_id: str, time: Optional[float] = Query(None)):
    match_repo.clear_drawings(match_id, timestamp=time)
    return {"status": "success"}

@router.post("/{match_id}/journal")
def update_journal(match_id: str, req: UpdateJournalRequest):
    match = match_repo.get_match(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    match.journal_notes = req.journal_notes
    match_repo.save_match(match)
    return {"status": "success", "journal_notes": match.journal_notes}
