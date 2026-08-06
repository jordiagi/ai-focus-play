from __future__ import annotations

from pydantic import BaseModel


class SourceCatalogItemResponse(BaseModel):
    catalog_id: str
    display_name: str
    relative_path: str
    duration_seconds: float = 0.0
    file_size_bytes: int | None = None
    last_modified_at: str | None = None
    details: str = ""


class SourceCatalogResponse(BaseModel):
    video_root: str
    items: list[SourceCatalogItemResponse]
