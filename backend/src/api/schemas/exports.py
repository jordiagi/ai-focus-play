from __future__ import annotations

from pydantic import BaseModel


class CreateExportRequest(BaseModel):
    profile: str = "short_highlight"
    overlay_mode: str = "none"  # none | target_marker


class ExportAcceptedResponse(BaseModel):
    output_id: str
    job_id: str


class ExportListItem(BaseModel):
    output_id: str
    profile: str
    overlay_mode: str
    status: str
    duration_s: float | None = None
    created_at: str


class ExportListResponse(BaseModel):
    outputs: list[ExportListItem]
