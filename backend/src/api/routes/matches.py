import os
import shutil
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from backend.src.domain.models.match import (
    Match, Highlight, Event, Drawing, RadarFrame, AnalyticsData, PlayerRoster
)
from backend.src.storage.repository import match_repo
from backend.src.services.pipeline.video_processor import VideoProcessor, MEDIA_DIR
from backend.src.services.pipeline.cv_engine import cv_engine

logger = logging.getLogger("api_matches")
router = APIRouter(prefix="/api/matches", tags=["matches"])

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

def process_uploaded_video_task(match_id: str, video_path: Path):
    """Background task orchestrating metadata probing, thumbnail, and CV analysis."""
    match = match_repo.get_match(match_id)
    if not match:
        return

    try:
        match.status = "processing"
        match.processing_step = "Probing video stream..."
        match.processing_progress = 10.0
        match_repo.save_match(match)

        # 1. Probing video metadata
        meta = VideoProcessor.get_video_metadata(video_path)
        match.duration_seconds = meta.get("duration", 90.0)

        # 2. Generating thumbnail
        thumb_path = MEDIA_DIR / f"{match_id}_thumb.jpg"
        if VideoProcessor.extract_thumbnail(video_path, thumb_path, time_sec=min(5.0, match.duration_seconds / 2.0)):
            match.thumbnail_url = f"/media/{thumb_path.name}"

        match.processing_step = "Tracking players and pitch calibration..."
        match.processing_progress = 30.0
        match_repo.save_match(match)

        # 3. CV pipeline: detection, tracking, field homography, event spotting
        def progress_cb(pct: float, step_name: str):
            m = match_repo.get_match(match_id)
            if m:
                m.processing_progress = 30.0 + (pct * 0.6)
                m.processing_step = step_name
                match_repo.save_match(m)

        radar_frames, events, highlights, analytics = cv_engine.process_video_match(
            video_path=video_path,
            duration=match.duration_seconds,
            home_team=match.home_team,
            away_team=match.away_team,
            progress_callback=progress_cb
        )

        for e in events:
            e.match_id = match_id
        for h in highlights:
            h.match_id = match_id

        # 4. Save results
        match_repo.save_radar_frames(match_id, radar_frames)
        match_repo.set_events(match_id, events)
        for h in highlights:
            # Cut subclips for top highlights
            clip_path = MEDIA_DIR / f"clip_{h.id}.mp4"
            if VideoProcessor.cut_clip(video_path, clip_path, h.start_time, h.end_time):
                h.clip_url = f"/media/{clip_path.name}"
            match_repo.add_highlight(h)

        match_repo.set_analytics(match_id, analytics)

        match.status = "ready"
        match.processing_step = "Analysis Complete"
        match.processing_progress = 100.0
        match_repo.save_match(match)
        logger.info(f"Successfully processed match {match_id}")

    except Exception as e:
        logger.error(f"Error in video processing task for {match_id}: {e}", exc_info=True)
        match.status = "error"
        match.error_message = str(e)
        match_repo.save_match(match)

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

    # Generate unique ID and save uploaded file
    import uuid
    match_id = str(uuid.uuid4())
    ext = Path(file.filename or "match.mp4").suffix or ".mp4"
    dest_path = MEDIA_DIR / f"{match_id}{ext}"

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    match = Match(
        id=match_id,
        title=title,
        home_team=home_team,
        away_team=away_team,
        date=date,
        video_url=f"/media/{dest_path.name}",
        panoramic_url=f"/media/{dest_path.name}",
        status="processing",
        processing_step="Ingesting video upload...",
        processing_progress=5.0,
        views_count=1
    )
    match_repo.save_match(match)

    background_tasks.add_task(process_uploaded_video_task, match_id, dest_path)
    return match

@router.get("/{match_id}/radar", response_model=List[RadarFrame])
def get_radar(
    match_id: str,
    time: Optional[float] = Query(None, description="Current timestamp in seconds to fetch nearby frame")
):
    frames = match_repo.get_radar_frames(match_id)
    if time is not None and frames:
        # Find closest frame
        closest = min(frames, key=lambda f: abs(f.timestamp - time))
        return [closest]
    return frames

@router.get("/{match_id}/analytics", response_model=AnalyticsData)
def get_analytics(match_id: str):
    analytics = match_repo.get_analytics(match_id)
    if not analytics:
        raise HTTPException(status_code=404, detail="Analytics not found for match")
    return analytics

@router.get("/{match_id}/highlights", response_model=List[Highlight])
def get_highlights(match_id: str):
    return match_repo.get_highlights(match_id)

@router.post("/{match_id}/highlights", response_model=Highlight)
def create_highlight(match_id: str, req: CreateHighlightRequest):
    raise HTTPException(status_code=403, detail="Read-only mode: Creating or writing new clips is disabled.")

@router.delete("/{match_id}/highlights/{highlight_id}")
def delete_highlight(match_id: str, highlight_id: str):
    raise HTTPException(status_code=403, detail="Read-only mode: Deleting clips is disabled.")


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
