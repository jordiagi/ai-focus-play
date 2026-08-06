from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from src.api.schemas.exports import (
    CreateExportRequest,
    ExportAcceptedResponse,
    ExportListItem,
    ExportListResponse,
)
from src.app.dependencies import export_service, output_repository, project_repository
from src.app.errors import AppError
from src.domain.models.project import AnalysisProject


router = APIRouter(prefix="/projects", tags=["exports"])


def _project_or_404(project_id: str) -> AnalysisProject:
    try:
        return project_repository().get(project_id)
    except KeyError as exc:
        raise AppError("Project not found", status_code=404) from exc


@router.post(
    "/{project_id}/exports",
    response_model=ExportAcceptedResponse,
    status_code=202,
)
def create_export(project_id: str, request: CreateExportRequest) -> ExportAcceptedResponse:
    project = _project_or_404(project_id)
    output, job_id = export_service().create(
        project, request.profile, request.overlay_mode
    )
    return ExportAcceptedResponse(output_id=output.output_id, job_id=job_id)


@router.get("/{project_id}/exports", response_model=ExportListResponse)
def list_exports(project_id: str) -> ExportListResponse:
    _project_or_404(project_id)
    outputs = output_repository().list_for_project(project_id)
    return ExportListResponse(
        outputs=[
            ExportListItem(
                output_id=output.output_id,
                profile=output.profile,
                overlay_mode=output.overlay_mode,
                status=output.status,
                duration_s=output.duration_s,
                created_at=output.created_at,
            )
            for output in outputs
        ]
    )


@router.get("/{project_id}/exports/{output_id}/download")
def download_export(project_id: str, output_id: str) -> FileResponse:
    _project_or_404(project_id)
    try:
        output = output_repository().get(output_id)
    except KeyError as exc:
        raise AppError("That reel is no longer available.", status_code=404) from exc
    if not output.file_path or not Path(output.file_path).is_file():
        raise AppError(
            "This reel isn't ready yet — it's still being put together.",
            status_code=409,
        )
    return FileResponse(
        output.file_path,
        media_type="video/mp4",
        filename=f"{output_id}.mp4",
    )
