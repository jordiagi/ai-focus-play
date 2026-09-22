from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator
import uuid
import time

class Drawing(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    match_id: str
    timestamp: float
    tool_type: str  # "arrow", "spotlight", "circle", "pen", "text"
    color: str = "#00E676"
    coordinates: List[Dict[str, float]] = []  # points: [{"x": 0.5, "y": 0.4}] in normalized 0..1
    text_label: Optional[str] = None
    created_at: float = Field(default_factory=time.time)

class Highlight(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    match_id: str
    title: str
    event_type: str  # "goal", "shot", "save", "foul", "corner", "kickoff", "custom"
    start_time: float
    end_time: float
    period: int = 1
    team: str = "home"  # "home", "away", "neutral"
    player_jersey: Optional[str] = None
    player_name: Optional[str] = None
    thumbnail_url: Optional[str] = None
    clip_url: Optional[str] = None
    is_ai_detected: bool = True
    tags: List[str] = []
    comments_count: int = 0
    created_at: float = Field(default_factory=time.time)

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    match_id: str
    timestamp: float
    period: int = 1
    event_type: str
    # "home" | "away" | "unknown". "unknown" is not a placeholder: a detector whose
    # team channel does not clear its random-team control must be able to decline, and
    # the team-aware metric rewards guessing over abstaining, so declining has to be
    # representable or the pipeline is pushed into fabricating a side.
    team: str
    player_jersey: Optional[str] = None
    player_name: Optional[str] = None
    description: str
    # Metres, 0..105 x 0..68 -- and OPTIONAL, because a detector that has no metric
    # calibration must be able to say so. The previous default of (52.5, 34.0) is the
    # centre spot, so any event ingested without a position silently claimed to have
    # happened on the centre spot. D-A failed to calibrate this footage five times over;
    # the D-B detectors work in panorama pixels and have no metres to give. None means
    # "not known", and consumers must skip rather than plot it.
    pitch_x: Optional[float] = None
    pitch_y: Optional[float] = None
    confidence: float = 0.8

class RadarPlayer(BaseModel):
    id: int
    team: str  # "home", "away", "referee"
    jersey: Optional[str] = None
    x: float  # 0..105m pitch
    y: float  # 0..68m pitch
    speed: float = 0.0

class RadarBall(BaseModel):
    x: float
    y: float
    z: float = 0.0
    detected: bool = True

class RadarFrame(BaseModel):
    timestamp: float
    players: List[RadarPlayer]
    ball: RadarBall

class ShotRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float
    period: int = 1
    team: str
    player_jersey: Optional[str] = None
    outcome: str  # "goal", "saved", "missed", "blocked"
    x: float  # pitch x
    y: float  # pitch y
    is_inside_box: bool
    label: str

class TeamStats(BaseModel):
    goals: int = 0
    shots: int = 0
    attempts: Optional[int] = None
    corners: Optional[int] = None
    free_kicks: Optional[int] = None
    throw_ins: Optional[int] = None
    fouls: Optional[int] = None
    penalties: Optional[int] = None
    tackles: Optional[int] = None
    passes_completed: Optional[int] = None
    possession_percent: float = 50.0
    possession_minutes: float = 0.0
    possession_won: Optional[int] = None

class AnalyticsData(BaseModel):
    home_stats: TeamStats
    away_stats: TeamStats
    shot_map: List[ShotRecord] = []
    pass_locations: Dict[str, Dict[str, float]] = {
        "home": {"defensive": 20.0, "middle": 55.0, "attacking": 25.0},
        "away": {"defensive": 15.0, "middle": 50.0, "attacking": 35.0}
    }
    possession_locations: Dict[str, Dict[str, float]] = {
        "home": {"defensive": 25.0, "middle": 50.0, "attacking": 25.0},
        "away": {"defensive": 20.0, "middle": 52.0, "attacking": 28.0}
    }
    pass_strings: Dict[str, List[int]] = {
        "home": [18, 12, 8, 4, 3, 2, 1, 0],
        "away": [24, 16, 11, 7, 4, 3, 2, 1]
    }
    heatmaps: Dict[str, List[Dict[str, Any]]] = {
        "home": [],
        "away": []
    }

class PlayerRoster(BaseModel):
    jersey: str
    name: str
    position: str  # "GK", "DEF", "MID", "FWD"
    is_starter: bool = True
    is_captain: bool = False
    is_player_of_match: bool = False
    minutes_played: int = 90

class EventCapability(BaseModel):
    status: Literal["detected", "not_attempted", "unavailable"]
    count: Optional[int] = Field(default=None, ge=0)
    reason: Optional[str] = None

    @model_validator(mode="after")
    def require_status_details(self):
        if self.status == "detected" and self.count is None:
            raise ValueError("detected event capabilities require a count")
        if self.status == "unavailable" and not self.reason:
            raise ValueError("unavailable event capabilities require a reason")
        return self

def default_event_capabilities() -> Dict[str, EventCapability]:
    """Capabilities of the current heuristic pipeline for legacy/new matches."""
    # "Out of play" was missing from this list until 2026-09-21. Veo reports it as a
    # type (it is 64 of the 447 events in the benchmark, the largest Tier A type), so a
    # surface that cannot name it cannot report it. Added rather than worked around.
    labels = [
        "Kickoff", "Goal", "Shot on goal", "Shot", "Save", "Corner", "Foul",
        "Free kick", "Goal kick", "Throw-in", "Out of play", "Tackle", "Interception",
        "Dribble", "Loose ball recovery", "Pass",
    ]
    detected = {"Kickoff", "Goal", "Shot"}
    return {
        label: EventCapability(
            status="detected" if label in detected else "not_attempted",
            count=0 if label in detected else None,
        )
        for label in labels
    }

class Match(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    home_team: str
    away_team: str
    home_score: int = 0
    away_score: int = 0
    date: str
    duration_seconds: float = 0.0
    status: str = "ready"  # "uploading", "processing", "ready", "error"
    processing_step: Optional[str] = None
    processing_progress: float = 100.0
    error_message: Optional[str] = None
    video_url: str
    panoramic_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    views_count: int = 1
    lineup: List[PlayerRoster] = []
    journal_notes: str = ""
    analysis_mode: str = "heuristic"         # "demo" | "heuristic" | "ml"
    analysis_confidence: str = "low"         # "low" | "medium" | "high"
    event_capabilities: Dict[str, EventCapability] = Field(default_factory=default_event_capabilities)
    created_at: float = Field(default_factory=time.time)
