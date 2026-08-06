from __future__ import annotations

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    name: str = Field(default="Untitled project", min_length=1, max_length=200)


class ProjectSummaryResponse(BaseModel):
    project_id: str
    name: str
    status: str
    source_id: str | None = None
    target_cluster_id: str | None = None
    updated_at: str


class AnalysisSummaryResponse(BaseModel):
    overall_status: str = "not_started"
    stages: list[dict] = Field(default_factory=list)
    no_readable_jersey_numbers: bool = False


class ProjectResponse(ProjectSummaryResponse):
    created_at: str
    jersey_hint: str | None = None
    source: dict | None = None
    analysis: AnalysisSummaryResponse = Field(default_factory=AnalysisSummaryResponse)


class SourceAttachRequest(BaseModel):
    file_path: str | None = None
    source_reference: str | None = None
    original_filename: str | None = None


class PipelineRunRequest(BaseModel):
    stages: list[str] | None = None
    force: bool = False


class JerseyHintRequest(BaseModel):
    jersey_hint: str | None = Field(default=None, pattern=r"^\d{1,3}$")


class TargetRequest(BaseModel):
    cluster_id: str = Field(min_length=1)


class TargetAdjustRequest(BaseModel):
    add_tracklet_ids: list[str] = Field(default_factory=list)
    remove_tracklet_ids: list[str] = Field(default_factory=list)


class TimelineSegmentPatchRequest(BaseModel):
    included: bool | None = None
    start_ts: float | None = None
    end_ts: float | None = None
