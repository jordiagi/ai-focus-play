from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.domain.models.project import utcnow


@dataclass
class ReelOutput:
    output_id: str
    project_id: str
    profile: str
    overlay_mode: str
    status: str = "queued"
    file_path: str | None = None
    duration_s: float | None = None
    segment_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


FocusReelOutput = ReelOutput
