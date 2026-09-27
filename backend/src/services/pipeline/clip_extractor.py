"""Autonomous Highlight Micro-Clip Extraction Engine (WP G12 / P1).

Identifies key match moments (verified goals, high-velocity goal-directed shots,
and period kickoffs), slices ~15-second MP4 micro-clips using fast stream copy,
extracts frame thumbnails, and builds verified Highlight records.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.src.domain.models.match import Event, Highlight, Match
from backend.src.services.pipeline.video_processor import VideoProcessor

logger = logging.getLogger("AutonomousClipExtractor")


class AutonomousClipExtractor:
    """Extracts standalone MP4 micro-clips and thumbnails for top AI-detected match moments."""

    def __init__(self, media_dir: Path, clip_window_before_s: float = 6.0, clip_window_after_s: float = 9.0):
        self.media_dir = Path(media_dir)
        self.window_before = clip_window_before_s
        self.window_after = clip_window_after_s

    def extract_highlight_clips(
        self,
        match: Match,
        events: List[Event],
        max_clips: int = 12,
        min_spacing_s: float = 10.0,
        video_start_offset: float = 0.0,
        force_reextract: bool = False,
    ) -> List[Highlight]:
        """Extract micro-clips for top events (goals, cards, subs, shots) and return structured Highlight models."""
        video_filename = Path(match.video_url).name if match.video_url else f"{match.id}.mp4"
        video_path = self.media_dir / video_filename
        has_video_file = video_path.exists() and video_path.is_file()

        # Prioritize Goals, Cards, Penalties, high-confidence Shots, Kickoffs, and Subs
        candidates: List[Event] = []
        for e in events:
            etype = e.event_type.lower()
            if any(k in etype for k in ("goal", "shot", "kickoff", "card", "penalty", "substitution")):
                candidates.append(e)

        # Priority ranking: Goal (0), Red/Penalty (1), Yellow Card (2), Shot (3), Kickoff (4), Sub (5)
        def priority_key(e: Event):
            et = e.event_type.lower()
            if "goal" in et:
                order = 0
            elif "red" in et or "penalty" in et:
                order = 1
            elif "yellow" in et or "card" in et:
                order = 2
            elif "shot" in et:
                order = 3
            elif "kickoff" in et:
                order = 4
            else:
                order = 5
            return (order, -e.confidence, e.timestamp)

        candidates.sort(key=priority_key)

        # Temporal Non-Maximum Suppression to avoid overlapping clips
        selected_events: List[Event] = []
        for cand in candidates:
            if len(selected_events) >= max_clips:
                break
            if not any(abs(cand.timestamp - s.timestamp) < min_spacing_s for s in selected_events):
                selected_events.append(cand)

        # Sort selected events chronologically
        selected_events.sort(key=lambda e: e.timestamp)

        highlights: List[Highlight] = []
        for idx, ev in enumerate(selected_events, start=1):
            st = max(0.0, ev.timestamp - self.window_before)
            et = min(match.duration_seconds, ev.timestamp + self.window_after)

            clip_name = f"clip_{match.id}_h{idx}.mp4"
            thumb_name = f"thumb_{match.id}_h{idx}.jpg"
            clip_path = self.media_dir / clip_name
            thumb_path = self.media_dir / thumb_name

            clip_url = match.video_url
            thumb_url = match.thumbnail_url or "/media/demo_thumb.jpg"

            if has_video_file:
                if force_reextract:
                    clip_path.unlink(missing_ok=True)
                    thumb_path.unlink(missing_ok=True)

                # Fast slice video clip if not already existing
                if not clip_path.exists():
                    try:
                        success = VideoProcessor.cut_clip(video_path, clip_path, start_time=st, end_time=et)
                        if success and clip_path.exists() and clip_path.stat().st_size > 1000:
                            clip_url = f"/media/{clip_name}"
                    except Exception as err:
                        logger.warning(f"Could not slice clip {clip_name}: {err}")

                if clip_path.exists():
                    clip_url = f"/media/{clip_name}"

                # Extract thumbnail
                if not thumb_path.exists():
                    try:
                        t_success = VideoProcessor.extract_thumbnail(video_path, thumb_path, time_sec=ev.timestamp)
                        if t_success and thumb_path.exists() and thumb_path.stat().st_size > 500:
                            thumb_url = f"/media/{thumb_name}"
                    except Exception as err:
                        logger.warning(f"Could not extract thumb {thumb_name}: {err}")

                if thumb_path.exists():
                    thumb_url = f"/media/{thumb_name}"

            # Format descriptive highlight title
            etype_display = ev.event_type
            team_name = match.home_team if ev.team == "home" else (match.away_team if ev.team == "away" else "")
            if ev.player_name:
                jersey_str = f" (#{ev.player_jersey})" if ev.player_jersey else ""
                title = f"{etype_display}: {ev.player_name}{jersey_str}"
            elif team_name:
                title = f"{etype_display} - {team_name}"
            else:
                title = f"{etype_display} Opportunity"

            highlights.append(
                Highlight(
                    id=f"hl_{match.id}_{idx}",
                    match_id=match.id,
                    title=title,
                    event_type=ev.event_type.lower(),
                    start_time=round(st, 1),
                    end_time=round(et, 1),
                    period=ev.period,
                    team=ev.team,
                    player_jersey=ev.player_jersey,
                    player_name=ev.player_name,
                    thumbnail_url=thumb_url,
                    clip_url=clip_url,
                    is_ai_detected=True,
                    tags=["ai_highlight", ev.event_type.lower()],
                    comments_count=0,
                    created_at=time.time(),
                )
            )

        return highlights
