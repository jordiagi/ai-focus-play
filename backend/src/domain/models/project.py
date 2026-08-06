from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class AnalysisProject:
    project_id: str
    name: str = "Untitled project"
    status: str = "draft"
    source_id: str | None = None
    jersey_hint: str | None = None
    target_cluster_id: str | None = None
    created_at: str = field(default_factory=utcnow)
    updated_at: str = field(default_factory=utcnow)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AnalysisProject":
        return cls(**payload)
