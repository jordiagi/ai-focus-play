from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_float(name: str, default: str) -> float:
    return float(os.getenv(name, default))


def _env_int(name: str, default: str) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: os.getenv("AI_FOCUS_ENV", "development"))
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("AI_FOCUS_DATA_DIR", ".local/data"))
    )
    db_path: Path = field(
        default_factory=lambda: Path(os.getenv("AI_FOCUS_DB_PATH", ".local/data/app.db"))
    )
    video_root: Path = field(
        default_factory=lambda: Path(os.getenv("AI_FOCUS_VIDEO_ROOT", "video"))
    )
    evidence_sample_count: int = field(
        default_factory=lambda: _env_int("AI_FOCUS_EVIDENCE_SAMPLE_COUNT", "10")
    )
    evidence_clip_seconds: int = field(
        default_factory=lambda: _env_int("AI_FOCUS_EVIDENCE_CLIP_SECONDS", "3")
    )
    retention_hours: int = field(
        default_factory=lambda: _env_int("AI_FOCUS_RETENTION_HOURS", "24")
    )
    analysis_fps: float = field(
        default_factory=lambda: _env_float("ANALYSIS_FPS", "6.0")
    )
    crop_interval_s: float = field(
        default_factory=lambda: _env_float("AI_FOCUS_CROP_INTERVAL_S", "2.0")
    )
    ocr_keyframes_per_tracklet: int = field(
        default_factory=lambda: _env_int("AI_FOCUS_OCR_KEYFRAMES_PER_TRACKLET", "8")
    )
    sam2_window_s: float = field(
        default_factory=lambda: _env_float("AI_FOCUS_SAM2_WINDOW_S", "60.0")
    )
    frames_cache_max: int = field(
        default_factory=lambda: _env_int("AI_FOCUS_FRAMES_CACHE_MAX", "500")
    )

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    value = Settings()
    value.ensure_directories()
    return value
