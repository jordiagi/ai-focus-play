from __future__ import annotations

from src.domain.models.detection import PlayerDetection


class HighlightService:
    def build_timeline(self, detections: list[PlayerDetection], output_profile: str) -> list[dict[str, float]]:
        approved = [d for d in detections if d.review_state in {"approved", "auto_accepted"}]
        limit = 3 if output_profile == "short_highlight" else 8
        return [{"start": d.start_time_seconds, "end": d.end_time_seconds} for d in approved[:limit]]

