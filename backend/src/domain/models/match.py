from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
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
    team: str  # "home", "away"
    player_jersey: Optional[str] = None
    player_name: Optional[str] = None
    description: str
    pitch_x: float = 52.5  # standard 0..105 meters
    pitch_y: float = 34.0  # standard 0..68 meters

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

class RadarFrame(BaseModel):
    timestamp: float
    players: List[RadarPlayer]
    ball: RadarBall

class ShotRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float
    period: int
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
    attempts: int = 0
    corners: int = 0
    free_kicks: int = 0
    throw_ins: int = 0
    fouls: int = 0
    penalties: int = 0
    tackles: int = 0
    passes_completed: int = 0
    possession_percent: float = 50.0
    possession_minutes: float = 0.0
    possession_won: int = 0

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
        # Distribution of strings from 3 to 10+ passes
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
    created_at: float = Field(default_factory=time.time)
