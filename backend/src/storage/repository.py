import json
import logging
import time
import math
from typing import Dict, List, Optional, Any
from pathlib import Path
from sqlalchemy.orm import Session
from backend.src.config import READ_ONLY, MEDIA_DIR
from backend.src.storage.database import (
    engine, SessionLocal, init_db,
    MatchDB, HighlightDB, EventDB, DrawingDB, LineupPlayerDB, RadarFrameDB, AnalyticsDB, ClubDB, JobDB
)
from backend.src.domain.models.match import (
    Match, Highlight, Event, Drawing, RadarFrame, RadarPlayer, RadarBall,
    ShotRecord, TeamStats, AnalyticsData, PlayerRoster
)

logger = logging.getLogger("repository")

class MatchRepository:
    def __init__(self):
        init_db()
        self._seed_if_empty()

    def get_db(self) -> Session:
        return SessionLocal()

    # Matches
    def list_matches(self) -> List[Match]:
        with self.get_db() as db:
            db_matches = db.query(MatchDB).order_by(MatchDB.created_at.desc()).all()
            return [self._match_db_to_domain(db, m) for m in db_matches]

    def get_match(self, match_id: str) -> Optional[Match]:
        with self.get_db() as db:
            m = db.query(MatchDB).filter(MatchDB.id == match_id).first()
            if not m:
                return None
            return self._match_db_to_domain(db, m)

    def save_match(self, match: Match):
        with self.get_db() as db:
            existing = db.query(MatchDB).filter(MatchDB.id == match.id).first()
            if existing:
                existing.title = match.title
                existing.home_team = match.home_team
                existing.away_team = match.away_team
                existing.home_score = match.home_score
                existing.away_score = match.away_score
                existing.date = match.date
                existing.duration_seconds = match.duration_seconds
                existing.status = match.status
                existing.processing_step = match.processing_step
                existing.processing_progress = match.processing_progress
                existing.error_message = match.error_message
                existing.video_url = match.video_url
                existing.panoramic_url = match.panoramic_url
                existing.thumbnail_url = match.thumbnail_url
                existing.views_count = match.views_count
                existing.journal_notes = match.journal_notes
                existing.analysis_mode = match.analysis_mode
                existing.analysis_confidence = match.analysis_confidence
            else:
                db_m = MatchDB(
                    id=match.id,
                    title=match.title,
                    home_team=match.home_team,
                    away_team=match.away_team,
                    home_score=match.home_score,
                    away_score=match.away_score,
                    date=match.date,
                    duration_seconds=match.duration_seconds,
                    status=match.status,
                    processing_step=match.processing_step,
                    processing_progress=match.processing_progress,
                    error_message=match.error_message,
                    video_url=match.video_url,
                    panoramic_url=match.panoramic_url,
                    thumbnail_url=match.thumbnail_url,
                    views_count=match.views_count,
                    journal_notes=match.journal_notes,
                    analysis_mode=match.analysis_mode,
                    analysis_confidence=match.analysis_confidence,
                    created_at=match.created_at,
                )
                db.add(db_m)
            db.commit()

    def delete_match(self, match_id: str):
        # 1. Collect and clean up media files securely (P2-6)
        media_root = MEDIA_DIR.resolve()
        with self.get_db() as db:
            m = db.query(MatchDB).filter(MatchDB.id == match_id).first()
            if not m:
                return

            files_to_remove: List[Path] = []
            if m.video_url and m.video_url.startswith("/media/"):
                files_to_remove.append(MEDIA_DIR / m.video_url.replace("/media/", ""))
            if m.thumbnail_url and m.thumbnail_url.startswith("/media/"):
                files_to_remove.append(MEDIA_DIR / m.thumbnail_url.replace("/media/", ""))
            
            highlights = db.query(HighlightDB).filter(HighlightDB.match_id == match_id).all()
            for h in highlights:
                if h.clip_url and h.clip_url.startswith("/media/"):
                    files_to_remove.append(MEDIA_DIR / h.clip_url.replace("/media/", ""))
                if h.thumbnail_url and h.thumbnail_url.startswith("/media/"):
                    files_to_remove.append(MEDIA_DIR / h.thumbnail_url.replace("/media/", ""))

            # Delete DB records (cascading deletes highlights, events, drawings, lineup, radar, analytics)
            db.delete(m)
            db.commit()

        # Safely unlink files after DB transaction completes
        for fpath in files_to_remove:
            try:
                # Guard unlink: must be within MEDIA_DIR and not demo fixtures
                resolved = fpath.resolve()
                if resolved.is_relative_to(media_root) and "demo_match" not in resolved.name and "demo_thumb" not in resolved.name:
                    if resolved.exists():
                        resolved.unlink(missing_ok=True)
                        logger.info(f"Unlinked match media file: {resolved}")
            except Exception as e:
                logger.warning(f"Failed to unlink file {fpath}: {e}")

    # Highlights
    def get_highlights(self, match_id: str) -> List[Highlight]:
        with self.get_db() as db:
            db_highlights = db.query(HighlightDB).filter(HighlightDB.match_id == match_id).order_by(HighlightDB.start_time.asc()).all()
            return [
                Highlight(
                    id=h.id,
                    match_id=h.match_id,
                    title=h.title,
                    event_type=h.event_type,
                    start_time=h.start_time,
                    end_time=h.end_time,
                    period=h.period,
                    team=h.team,
                    player_jersey=h.player_jersey,
                    player_name=h.player_name,
                    thumbnail_url=h.thumbnail_url,
                    clip_url=h.clip_url,
                    is_ai_detected=h.is_ai_detected,
                    tags=json.loads(h.tags) if h.tags else [],
                    comments_count=h.comments_count,
                    created_at=h.created_at
                )
                for h in db_highlights
            ]

    def add_highlight(self, highlight: Highlight, *, internal: bool = False):
        if READ_ONLY and not internal:
            raise PermissionError("Read-only mode: Creating or writing new clips is disabled.")
        with self.get_db() as db:
            db_h = HighlightDB(
                id=highlight.id,
                match_id=highlight.match_id,
                title=highlight.title,
                event_type=highlight.event_type,
                start_time=highlight.start_time,
                end_time=highlight.end_time,
                period=highlight.period,
                team=highlight.team,
                player_jersey=highlight.player_jersey,
                player_name=highlight.player_name,
                thumbnail_url=highlight.thumbnail_url,
                clip_url=highlight.clip_url,
                is_ai_detected=highlight.is_ai_detected,
                tags=json.dumps(highlight.tags),
                comments_count=highlight.comments_count,
                created_at=highlight.created_at
            )
            db.add(db_h)
            db.commit()
            return highlight

    def delete_highlight(self, match_id: str, highlight_id: str, *, internal: bool = False):
        if READ_ONLY and not internal:
            raise PermissionError("Read-only mode: Deleting clips is disabled.")
        with self.get_db() as db:
            h = db.query(HighlightDB).filter(HighlightDB.match_id == match_id, HighlightDB.id == highlight_id).first()
            if h:
                db.delete(h)
                db.commit()

    # Events
    def get_events(self, match_id: str) -> List[Event]:
        with self.get_db() as db:
            db_events = db.query(EventDB).filter(EventDB.match_id == match_id).order_by(EventDB.timestamp.asc()).all()
            return [
                Event(
                    id=e.id,
                    match_id=e.match_id,
                    timestamp=e.timestamp,
                    period=e.period,
                    event_type=e.event_type,
                    team=e.team,
                    player_jersey=e.player_jersey,
                    player_name=e.player_name,
                    description=e.description,
                    pitch_x=e.pitch_x,
                    pitch_y=e.pitch_y,
                    confidence=getattr(e, 'confidence', 0.8)
                )
                for e in db_events
            ]

    def set_events(self, match_id: str, events: List[Event]):
        with self.get_db() as db:
            db.query(EventDB).filter(EventDB.match_id == match_id).delete()
            for e in events:
                db.add(EventDB(
                    id=e.id,
                    match_id=match_id,
                    timestamp=e.timestamp,
                    period=e.period,
                    event_type=e.event_type,
                    team=e.team,
                    player_jersey=e.player_jersey,
                    player_name=e.player_name,
                    description=e.description,
                    pitch_x=e.pitch_x,
                    pitch_y=e.pitch_y,
                    confidence=e.confidence
                ))
            db.commit()

    # Drawings
    def get_drawings(self, match_id: str) -> List[Drawing]:
        with self.get_db() as db:
            db_drawings = db.query(DrawingDB).filter(DrawingDB.match_id == match_id).order_by(DrawingDB.timestamp.asc()).all()
            return [
                Drawing(
                    id=d.id,
                    match_id=d.match_id,
                    timestamp=d.timestamp,
                    tool_type=d.tool_type,
                    color=d.color,
                    coordinates=json.loads(d.coordinates) if d.coordinates else [],
                    text_label=d.text_label,
                    created_at=d.created_at
                )
                for d in db_drawings
            ]

    def add_drawing(self, drawing: Drawing):
        with self.get_db() as db:
            db.add(DrawingDB(
                id=drawing.id,
                match_id=drawing.match_id,
                timestamp=drawing.timestamp,
                tool_type=drawing.tool_type,
                color=drawing.color,
                coordinates=json.dumps(drawing.coordinates),
                text_label=drawing.text_label,
                created_at=drawing.created_at
            ))
            db.commit()
            return drawing

    def delete_drawing(self, match_id: str, drawing_id: str):
        with self.get_db() as db:
            db.query(DrawingDB).filter(DrawingDB.match_id == match_id, DrawingDB.id == drawing_id).delete()
            db.commit()

    def clear_drawings(self, match_id: str, timestamp: Optional[float] = None):
        with self.get_db() as db:
            q = db.query(DrawingDB).filter(DrawingDB.match_id == match_id)
            if timestamp is not None:
                q = q.filter(DrawingDB.timestamp >= timestamp - 1.0, DrawingDB.timestamp <= timestamp + 1.0)
            q.delete()
            db.commit()

    # Analytics
    def get_analytics(self, match_id: str) -> Optional[AnalyticsData]:
        with self.get_db() as db:
            db_an = db.query(AnalyticsDB).filter(AnalyticsDB.match_id == match_id).first()
            if not db_an:
                return None
            return AnalyticsData(**json.loads(db_an.data))

    def set_analytics(self, match_id: str, data: AnalyticsData):
        with self.get_db() as db:
            existing = db.query(AnalyticsDB).filter(AnalyticsDB.match_id == match_id).first()
            if existing:
                existing.data = json.dumps(data.model_dump())
            else:
                db.add(AnalyticsDB(match_id=match_id, data=json.dumps(data.model_dump())))
            db.commit()

    # Radar Frames
    def get_radar_frames(self, match_id: str) -> List[RadarFrame]:
        with self.get_db() as db:
            db_frames = db.query(RadarFrameDB).filter(RadarFrameDB.match_id == match_id).order_by(RadarFrameDB.timestamp.asc()).all()
            return [RadarFrame(**json.loads(f.data)) for f in db_frames]

    def get_radar_frames_window(self, match_id: str, start_time: float, end_time: float) -> List[RadarFrame]:
        with self.get_db() as db:
            db_frames = (
                db.query(RadarFrameDB)
                .filter(
                    RadarFrameDB.match_id == match_id,
                    RadarFrameDB.timestamp >= start_time,
                    RadarFrameDB.timestamp <= end_time
                )
                .order_by(RadarFrameDB.timestamp.asc())
                .all()
            )
            return [RadarFrame(**json.loads(f.data)) for f in db_frames]

    def get_radar_meta(self, match_id: str) -> Dict[str, Any]:
        with self.get_db() as db:
            count = db.query(RadarFrameDB).filter(RadarFrameDB.match_id == match_id).count()
            first = db.query(RadarFrameDB).filter(RadarFrameDB.match_id == match_id).order_by(RadarFrameDB.timestamp.asc()).first()
            last = db.query(RadarFrameDB).filter(RadarFrameDB.match_id == match_id).order_by(RadarFrameDB.timestamp.desc()).first()
            duration = (last.timestamp - first.timestamp) if (first and last) else 0.0
            sample_fps = (count / duration) if (duration > 0 and count > 1) else 2.0
            return {
                "match_id": match_id,
                "frame_count": count,
                "duration": round(duration, 2),
                "sample_fps": round(sample_fps, 2)
            }

    def save_radar_frames(self, match_id: str, frames: List[RadarFrame]):
        with self.get_db() as db:
            db.query(RadarFrameDB).filter(RadarFrameDB.match_id == match_id).delete()
            db_objects = [
                RadarFrameDB(
                    match_id=match_id,
                    timestamp=f.timestamp,
                    data=json.dumps(f.model_dump())
                )
                for f in frames
            ]
            db.add_all(db_objects)
            db.commit()

    # Team Swap (P1-2)
    def swap_teams(self, match_id: str):
        with self.get_db() as db:
            # 1. Swap events team
            events = db.query(EventDB).filter(EventDB.match_id == match_id).all()
            for e in events:
                if e.team == "home":
                    e.team = "away"
                elif e.team == "away":
                    e.team = "home"

            # 2. Swap highlights team
            highlights = db.query(HighlightDB).filter(HighlightDB.match_id == match_id).all()
            for h in highlights:
                if h.team == "home":
                    h.team = "away"
                elif h.team == "away":
                    h.team = "home"

            # 3. Swap radar frame player teams
            radar_frames = db.query(RadarFrameDB).filter(RadarFrameDB.match_id == match_id).all()
            for rf in radar_frames:
                frame_dict = json.loads(rf.data)
                for p in frame_dict.get("players", []):
                    if p.get("team") == "home":
                        p["team"] = "away"
                    elif p.get("team") == "away":
                        p["team"] = "home"
                rf.data = json.dumps(frame_dict)

            # 4. Swap analytics
            an = db.query(AnalyticsDB).filter(AnalyticsDB.match_id == match_id).first()
            if an:
                adata = json.loads(an.data)
                home_st = adata.get("home_stats")
                away_st = adata.get("away_stats")
                adata["home_stats"] = away_st
                adata["away_stats"] = home_st

                pass_locs = adata.get("pass_locations", {})
                h_pass = pass_locs.get("home")
                a_pass = pass_locs.get("away")
                if h_pass and a_pass:
                    adata["pass_locations"] = {"home": a_pass, "away": h_pass}

                pos_locs = adata.get("possession_locations", {})
                h_pos = pos_locs.get("home")
                a_pos = pos_locs.get("away")
                if h_pos and a_pos:
                    adata["possession_locations"] = {"home": a_pos, "away": h_pos}

                for s in adata.get("shot_map", []):
                    if s.get("team") == "home":
                        s["team"] = "away"
                    elif s.get("team") == "away":
                        s["team"] = "home"

                an.data = json.dumps(adata)

            # 5. Swap score on match
            m = db.query(MatchDB).filter(MatchDB.id == match_id).first()
            if m:
                m.home_score, m.away_score = m.away_score, m.home_score

            db.commit()

    # Background Jobs (P2-4)
    def create_job(self, match_id: str, kind: str = "cv_analysis") -> str:
        import uuid
        job_id = str(uuid.uuid4())
        job = JobDB(
            id=job_id,
            match_id=match_id,
            kind=kind,
            status="running",
            progress=0.0,
            step="Initializing analysis...",
            started_at=time.time()
        )
        with self.get_db() as db:
            db.add(job)
            db.commit()
        return job_id

    def update_job(self, job_id: str, status: Optional[str] = None, progress: Optional[float] = None, step: Optional[str] = None, error: Optional[str] = None):
        with self.get_db() as db:
            j = db.query(JobDB).filter(JobDB.id == job_id).first()
            if j:
                if status is not None:
                    j.status = status
                    if status in ("completed", "failed", "interrupted"):
                        j.finished_at = time.time()
                if progress is not None:
                    j.progress = progress
                if step is not None:
                    j.step = step
                if error is not None:
                    j.error = error
                db.commit()

    def get_job_by_match(self, match_id: str) -> Optional[Dict[str, Any]]:
        with self.get_db() as db:
            j = db.query(JobDB).filter(JobDB.match_id == match_id).order_by(JobDB.started_at.desc()).first()
            if not j:
                return None
            return {
                "id": j.id,
                "match_id": j.match_id,
                "kind": j.kind,
                "status": j.status,
                "progress": j.progress,
                "step": j.step,
                "error": j.error
            }

    def _match_db_to_domain(self, db: Session, m: MatchDB) -> Match:
        db_lineup = db.query(LineupPlayerDB).filter(LineupPlayerDB.match_id == m.id).all()
        lineup = [
            PlayerRoster(
                jersey=p.jersey,
                name=p.name,
                position=p.position,
                is_starter=p.is_starter,
                is_captain=p.is_captain,
                is_player_of_match=p.is_player_of_match,
                minutes_played=p.minutes_played
            )
            for p in db_lineup
        ]
        return Match(
            id=m.id,
            title=m.title,
            home_team=m.home_team,
            away_team=m.away_team,
            home_score=m.home_score,
            away_score=m.away_score,
            date=m.date,
            duration_seconds=m.duration_seconds,
            status=m.status,
            processing_step=m.processing_step,
            processing_progress=m.processing_progress,
            error_message=m.error_message,
            video_url=m.video_url,
            panoramic_url=m.panoramic_url,
            thumbnail_url=m.thumbnail_url,
            views_count=m.views_count,
            lineup=lineup,
            journal_notes=m.journal_notes,
            analysis_mode=getattr(m, 'analysis_mode', 'heuristic') or 'heuristic',
            analysis_confidence=getattr(m, 'analysis_confidence', 'low') or 'low',
            created_at=m.created_at
        )

    def _seed_if_empty(self):
        with self.get_db() as db:
            demo_m = db.query(MatchDB).filter(MatchDB.id == "demo-arlington-skyline").first()
            if demo_m and demo_m.analysis_mode != "demo":
                demo_m.analysis_mode = "demo"
                db.commit()

            if db.query(MatchDB).count() > 0:
                return

            default_id = "demo-arlington-skyline"
            match = MatchDB(
                id=default_id,
                title="Arlington SA U16B ECNL (26-27) vs. Skyline U16B ECNL",
                home_team="Arlington SA U16B ECNL",
                away_team="Skyline U16B ECNL",
                home_score=3,
                away_score=3,
                date="Sep 13, 2026",
                duration_seconds=90.0,
                status="ready",
                processing_step="Complete",
                processing_progress=100.0,
                video_url="/media/demo_match.mp4",
                panoramic_url="/media/demo_match.mp4",
                thumbnail_url="/media/demo_thumb.jpg",
                views_count=95,
                journal_notes="Great high-press organization in the first half. Focus on transitional recovery when attacking wings overextend.",
                analysis_mode="demo",
                analysis_confidence="low",
                created_at=time.time()
            )
            db.add(match)

            # Roster
            roster_data = [
                ("GK", "Alex Reed", "GK", True, False, False),
                ("1", "Lucas Gomez", "GK", False, False, False),
                ("2", "Mateo Silva", "DEF", True, False, False),
                ("4", "Julian Vance", "DEF", True, True, False),
                ("6", "Noah Bennett", "DEF", True, False, False),
                ("8", "Carlos Mendez", "MID", True, False, False),
                ("10", "Eric Jordi", "MID", True, False, True),
                ("12", "Samir Patel", "MID", True, False, False),
                ("13", "Liam O'Connor", "FWD", False, False, False),
                ("14", "Diego Morales", "FWD", True, False, False),
                ("16", "David Kim", "MID", False, False, False),
                ("18", "Ethan Ross", "FWD", True, False, False),
                ("20", "Marcus Cole", "DEF", False, False, False),
                ("24", "Oliver Brown", "MID", False, False, False),
                ("28", "Zachary Hall", "MID", True, False, False),
                ("32", "Gabriel Santos", "FWD", False, False, False),
                ("44", "Jack Wilson", "DEF", False, False, False),
            ]
            for j, name, pos, starter, capt, motm in roster_data:
                db.add(LineupPlayerDB(
                    id=f"{default_id}_{j}",
                    match_id=default_id,
                    jersey=j,
                    name=name,
                    position=pos,
                    is_starter=starter,
                    is_captain=capt,
                    is_player_of_match=motm,
                    minutes_played=90 if starter else 25
                ))

            # Highlights
            highlights_seed = [
                ("h1", "Goal - 10 Eric Jordi", "goal", 12.0, 24.0, 1, "home", "10", "Eric Jordi", ["Goal", "Inside Box", "Top Corner"]),
                ("h2", "Shot on Goal - 14 Diego Morales", "shot", 32.0, 42.0, 1, "home", "14", "Diego Morales", ["Shot on Target", "Save"]),
                ("h3", "Goal - Skyline Counterattack", "goal", 48.0, 60.0, 1, "away", "9", "Skyline Striker", ["Goal", "Counter"]),
                ("h4", "Corner Kick & Header Chance", "corner", 66.0, 78.0, 2, "home", "8", "Carlos Mendez", ["Corner", "Header"]),
                ("h5", "Crucial Tackle & Transition - 4 Julian Vance", "foul", 80.0, 88.0, 2, "home", "4", "Julian Vance", ["Tackle", "Recovery"]),
            ]
            for hid, title, etype, st, et, per, tm, j, pname, tags in highlights_seed:
                db.add(HighlightDB(
                    id=f"{default_id}_{hid}",
                    match_id=default_id,
                    title=title,
                    event_type=etype,
                    start_time=st,
                    end_time=et,
                    period=per,
                    team=tm,
                    player_jersey=j,
                    player_name=pname,
                    thumbnail_url="/media/demo_thumb.jpg",
                    clip_url="/media/demo_match.mp4",
                    is_ai_detected=True,
                    tags=json.dumps(tags),
                    comments_count=0,
                    created_at=time.time()
                ))

            # Chronological events
            events_seed = [
                ("e1", 2.0, 1, "Kickoff", "home", "10", "Kickoff by #10 Eric Jordi", 52.5, 34.0),
                ("e2", 7.5, 1, "Pass", "home", "4", "Pass from Julian Vance to Carlos Mendez", 40.0, 28.0),
                ("e3", 18.0, 1, "Goal", "home", "10", "Goal scored by #10 Eric Jordi into top right", 98.0, 32.0),
                ("e4", 25.0, 1, "Tackle", "home", "6", "Clean challenge won on left wing", 45.0, 12.0),
                ("e5", 36.0, 1, "Shot", "home", "14", "Shot on goal saved by goalkeeper", 88.0, 35.0),
                ("e6", 53.0, 1, "Goal", "away", "9", "Goal by Skyline off fast break", 12.0, 33.0),
                ("e7", 71.0, 2, "Corner Kick", "home", "8", "In-swinging corner delivered into 6-yard box", 105.0, 2.0),
                ("e8", 84.0, 2, "Interception", "home", "28", "Turnover forced in central midfield", 55.0, 36.0),
            ]
            for eid, t, per, etype, tm, j, desc, px, py in events_seed:
                db.add(EventDB(
                    id=f"{default_id}_{eid}",
                    match_id=default_id,
                    timestamp=t,
                    period=per,
                    event_type=etype,
                    team=tm,
                    player_jersey=j,
                    description=desc,
                    pitch_x=px,
                    pitch_y=py,
                    confidence=0.9
                ))

            # Analytics
            analytics_payload = {
                "home_stats": {
                    "goals": 3, "shots": 10, "attempts": 13, "corners": 6, "free_kicks": 7, "throw_ins": 24,
                    "fouls": 8, "penalties": 0, "tackles": 41, "passes_completed": 203,
                    "possession_percent": 38.0, "possession_minutes": 14.0, "possession_won": 150
                },
                "away_stats": {
                    "goals": 3, "shots": 9, "attempts": 12, "corners": 3, "free_kicks": 8, "throw_ins": 14,
                    "fouls": 7, "penalties": 0, "tackles": 43, "passes_completed": 283,
                    "possession_percent": 62.0, "possession_minutes": 22.0, "possession_won": 151
                },
                "shot_map": [
                    {"id": "s1", "timestamp": 18.0, "period": 1, "team": "home", "player_jersey": "10", "outcome": "goal", "x": 98.0, "y": 32.0, "is_inside_box": True, "label": "Goal at 18s (Inside Box)"},
                    {"id": "s2", "timestamp": 36.0, "period": 1, "team": "home", "player_jersey": "14", "outcome": "saved", "x": 88.0, "y": 35.0, "is_inside_box": True, "label": "Shot Saved at 36s"},
                    {"id": "s3", "timestamp": 42.0, "period": 1, "team": "home", "player_jersey": "8", "outcome": "missed", "x": 80.0, "y": 24.0, "is_inside_box": False, "label": "Shot Wide at 42s"},
                    {"id": "s4", "timestamp": 53.0, "period": 1, "team": "away", "player_jersey": "9", "outcome": "goal", "x": 12.0, "y": 33.0, "is_inside_box": True, "label": "Skyline Goal at 53s"},
                    {"id": "s5", "timestamp": 72.0, "period": 2, "team": "home", "player_jersey": "18", "outcome": "blocked", "x": 92.0, "y": 38.0, "is_inside_box": True, "label": "Shot Blocked at 72s"}
                ],
                "pass_locations": {
                    "home": {"defensive": 7.0, "middle": 78.0, "attacking": 15.0},
                    "away": {"defensive": 12.0, "middle": 68.0, "attacking": 20.0}
                },
                "possession_locations": {
                    "home": {"defensive": 33.0, "middle": 44.0, "attacking": 23.0},
                    "away": {"defensive": 22.0, "middle": 54.0, "attacking": 24.0}
                },
                "pass_strings": {
                    "home": [18, 12, 8, 4, 3, 2, 1, 0],
                    "away": [24, 16, 11, 7, 4, 3, 2, 1]
                }
            }
            db.add(AnalyticsDB(match_id=default_id, data=json.dumps(analytics_payload)))

            # 2D Radar frames
            fps = 2.0
            home_jerseys = ["GK", "2", "4", "6", "8", "10", "12", "14", "18", "28"]
            away_jerseys = ["1", "3", "5", "7", "9", "11", "15", "17", "19", "21"]
            home_bases = [(5.0, 34.0), (25.0, 12.0), (22.0, 26.0), (22.0, 42.0), (25.0, 56.0), (48.0, 22.0), (54.0, 34.0), (48.0, 46.0), (75.0, 16.0), (82.0, 34.0)]
            away_bases = [(100.0, 34.0), (80.0, 12.0), (82.0, 26.0), (82.0, 42.0), (80.0, 56.0), (56.0, 24.0), (52.0, 34.0), (56.0, 44.0), (32.0, 18.0), (26.0, 34.0)]

            radar_objects = []
            for i in range(int(90.0 * fps)):
                t = i / fps
                ball_x = 52.5 + 35.0 * math.sin(t * 0.15) + 8.0 * math.sin(t * 0.6)
                ball_y = 34.0 + 20.0 * math.cos(t * 0.12)
                players = []
                for p_idx, (bx, by) in enumerate(home_bases):
                    shift_x = (ball_x - 52.5) * 0.25 + 2.0 * math.sin(t * 0.5 + p_idx)
                    shift_y = (ball_y - 34.0) * 0.2 + 1.5 * math.cos(t * 0.4 + p_idx)
                    players.append({
                        "id": p_idx + 1, "team": "home", "jersey": home_jerseys[p_idx],
                        "x": round(max(2.0, min(103.0, bx + shift_x)), 1),
                        "y": round(max(2.0, min(66.0, by + shift_y)), 1),
                        "speed": round(2.0 + 1.5 * math.sin(t + p_idx), 1)
                    })
                for p_idx, (bx, by) in enumerate(away_bases):
                    shift_x = (ball_x - 52.5) * 0.25 - 2.0 * math.sin(t * 0.5 + p_idx)
                    shift_y = (ball_y - 34.0) * 0.2 - 1.5 * math.cos(t * 0.4 + p_idx)
                    players.append({
                        "id": 100 + p_idx + 1, "team": "away", "jersey": away_jerseys[p_idx],
                        "x": round(max(2.0, min(103.0, bx + shift_x)), 1),
                        "y": round(max(2.0, min(66.0, by + shift_y)), 1),
                        "speed": round(2.0 + 1.2 * math.cos(t + p_idx), 1)
                    })
                frame_data = {
                    "timestamp": round(t, 2),
                    "players": players,
                    "ball": {"x": round(ball_x, 1), "y": round(ball_y, 1), "z": 0.0, "detected": True}
                }
                radar_objects.append(RadarFrameDB(
                    match_id=default_id,
                    timestamp=round(t, 2),
                    data=json.dumps(frame_data)
                ))

            db.add_all(radar_objects)
            db.commit()
            logger.info("Successfully seeded SQLite database with Arlington vs Skyline match data.")

# Global match repository instance backed by SQLite
match_repo = MatchRepository()

def get_repository() -> MatchRepository:
    return match_repo
