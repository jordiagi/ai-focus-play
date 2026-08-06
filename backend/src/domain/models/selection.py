from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from src.domain.models.project import utcnow


@dataclass
class UserClick:
    click_id: str
    project_id: str
    ts: float
    x_norm: float
    y_norm: float
    label: str
    status: str
    resolved_tracklet_id: str | None = None
    sam2_job_id: str | None = None
    created_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AppearanceSegment:
    segment_id: str
    project_id: str
    cluster_id: str
    start_ts: float
    end_ts: float
    score: float | None = None
    included: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
