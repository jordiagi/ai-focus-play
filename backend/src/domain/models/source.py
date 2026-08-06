from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class VideoSource:
    source_id: str
    source_type: str
    display_name: str
    original_uri: str
    source_reference: str = ""
    relative_path: str | None = None
    duration_seconds: float = 0.0
    file_size_bytes: int | None = None
    last_modified_at: str | None = None
    access_status: str = "pending"
    ingest_status: str = "pending"
    cleanup_status: str = "pending"
    validation_status: str = "available"
    validation_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "VideoSource":
        return cls(**payload)


@dataclass
class SourceCatalogItem:
    catalog_id: str
    display_name: str
    relative_path: str
    duration_seconds: float = 0.0
    file_size_bytes: int | None = None
    last_modified_at: str | None = None
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
