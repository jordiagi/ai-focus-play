from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Request
from starlette.datastructures import UploadFile

from src.api.schemas.projects import PipelineRunRequest, SourceAttachRequest
from src.api.schemas.sources import SourceCatalogResponse
from src.app.dependencies import (
    artifact_service,
    job_repository,
    job_service,
    project_repository,
    settings,
    source_catalog_service,
    source_repository,
)
from src.app.errors import AppError
from src.domain.models.video import SourceVideo
from src.services.video_ingest_service import ingest_video


router = APIRouter(tags=["sources"])
PIPELINE_STAGES = [
    "proxy",
    "detect_track",
    "embed_cluster",
    "jersey_ocr",
    "assemble_candidates",
]


@router.get("/sources/local", response_model=SourceCatalogResponse)
def list_local_sources() -> SourceCatalogResponse:
    return SourceCatalogResponse(
        video_root=str(settings().video_root),
        items=[item.to_dict() for item in source_catalog_service().list_local_videos()],
    )


@router.post("/projects/{project_id}/source", status_code=202)
async def attach_source(project_id: str, request: Request) -> dict:
    _project_or_404(project_id)
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise AppError("Choose a video file to continue", status_code=400)
        path = await _save_upload(project_id, upload)
        original_filename = upload.filename or path.name
    else:
        payload = SourceAttachRequest(**(await request.json()))
        value = payload.file_path or payload.source_reference
        if not value:
            raise AppError("Choose a video file to continue", status_code=400)
        path = _resolve_source_path(value)
        original_filename = payload.original_filename or path.name
    result = ingest_video(str(path), original_filename)
    if not result.validated:
        raise AppError(
            "That file doesn't look like a playable video. Your file wasn't changed — "
            "try re-exporting it as MP4.",
            status_code=400,
        )
    source = SourceVideo(
        source_id=result.source_id,
        project_id=project_id,
        file_path=str(path),
        original_filename=result.original_filename,
        content_hash=_sha256(path),
        duration_s=result.stream.duration_seconds,
        fps=result.stream.fps,
        width=result.stream.width,
        height=result.stream.height,
        codec=result.stream.codec,
    )
    source_repository().insert(source)
    project_repository().set_source(project_id, source.source_id)
    project_repository().update_status(project_id, "analyzing")
    jobs = job_service().enqueue_chain(project_id, PIPELINE_STAGES)
    job_service().start_next()
    return {
        "source": source.to_dict(),
        "jobs_queued": [{"job_id": job.job_id, "stage": job.stage} for job in jobs],
    }


@router.post("/projects/{project_id}/pipeline/run", status_code=202)
def run_pipeline(project_id: str, request: PipelineRunRequest) -> dict:
    _project_or_404(project_id)
    requested = request.stages or PIPELINE_STAGES
    invalid = set(requested) - set(PIPELINE_STAGES)
    if invalid:
        raise AppError("Choose a valid analysis step to retry", status_code=400)
    latest = {
        job.stage: job
        for job in job_repository().list_for_project(project_id)
    }
    stages = [
        stage
        for stage in requested
        if request.force
        or stage not in latest
        or latest[stage].status != "succeeded"
    ]
    jobs = job_service().enqueue_chain(project_id, stages)
    job_service().start_next()
    return {"jobs_queued": [{"job_id": job.job_id, "stage": job.stage} for job in jobs]}


def _project_or_404(project_id: str) -> None:
    try:
        project_repository().get(project_id)
    except KeyError as exc:
        raise AppError("Project not found", status_code=404) from exc


def _resolve_source_path(value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    root = settings().video_root.resolve()
    resolved = (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise AppError("Choose a video inside the configured video folder", status_code=400)
    return resolved


async def _save_upload(project_id: str, upload: UploadFile) -> Path:
    name = Path(upload.filename or "match.mp4").name
    suffix = Path(name).suffix or ".mp4"
    path = artifact_service().project_dir(project_id) / "source" / f"{uuid4()}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        while chunk := await upload.read(1024 * 1024):
            handle.write(chunk)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
