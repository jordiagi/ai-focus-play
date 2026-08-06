from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.domain.models.project import utcnow


@dataclass
class SourceVideo:
    source_id: str
    project_id: str
    file_path: str
    original_filename: str | None = None
    content_hash: str | None = None
    duration_s: float | None = None
    fps: float | None = None
    width: int | None = None
    height: int | None = None
    codec: str | None = None
    proxy_path: str | None = None
    proxy_status: str = "pending"
    created_at: str = field(default_factory=utcnow)

    @property
    def duration_seconds(self) -> float:
        return float(self.duration_s or 0.0)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceVideo":
        return cls(**payload)
