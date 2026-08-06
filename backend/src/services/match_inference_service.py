from __future__ import annotations

from src.domain.models.source import VideoSource


class MatchInferenceService:
    def infer(self, source: VideoSource) -> dict[str, object]:
        duration = max(0.0, float(source.duration_seconds or 0.0))
        confidence = "medium" if duration >= 1800 else "low"
        reasons = [] if confidence == "medium" else ["Source duration is short or unavailable"]
        return {
            "start_seconds": 0.0,
            "end_seconds": duration if duration > 0 else 7200.0,
            "confidence": confidence,
            "summary": "Using the full playable source automatically; no manual match window is required.",
            "uncertainty_reasons": reasons,
        }
