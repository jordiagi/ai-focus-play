from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from src.domain.models.project import utcnow


class JobStage(StrEnum):
    PROXY = "proxy"
    DETECT_TRACK = "detect_track"
    EMBED_CLUSTER = "embed_cluster"
    JERSEY_OCR = "jersey_ocr"
    ASSEMBLE_CANDIDATES = "assemble_candidates"
    SAM2_REFINE = "sam2_refine"
    EXPORT = "export"
    SLEEP_DEMO = "sleep_demo"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineJob:
    job_id: str
    project_id: str
    stage: str
    status: str = JobStatus.QUEUED
    progress_pct: float = 0.0
    progress_message: str | None = None
    checkpoint_json: str | None = None
    params_json: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=utcnow)
    started_at: str | None = None
    finished_at: str | None = None

    @property
    def checkpoint(self) -> dict[str, Any]:
        return json.loads(self.checkpoint_json) if self.checkpoint_json else {}

    @property
    def params(self) -> dict[str, Any]:
        return json.loads(self.params_json) if self.params_json else {}

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stage"] = str(self.stage)
        payload["status"] = str(self.status)
        return payload
