from __future__ import annotations

from pydantic import BaseModel


class StartAnalysisRequest(BaseModel):
    processing_mode: str


class ReviewDecisionInput(BaseModel):
    decision: str
    reviewer_note: str = ""


class PlayerDetectionResponse(BaseModel):
    detection_id: str
    start_time_seconds: float
    end_time_seconds: float
    team_match_confidence: float
    identity_confidence: float
    review_state: str
    visual_cues_used: list[str]

