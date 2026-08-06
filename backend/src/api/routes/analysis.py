from __future__ import annotations

from fastapi import APIRouter

from src.api.routes.projects import build_response
from src.api.schemas.detections import PlayerDetectionResponse, StartAnalysisRequest
from src.app.dependencies import analysis_service, job_repository, project_repository

router = APIRouter(tags=["analysis"])


@router.post("/projects/{project_id}/analysis", response_model=dict, status_code=202)
def start_analysis(project_id: str, request: StartAnalysisRequest) -> dict:
    project = project_repository().get_project(project_id)
    updated = analysis_service(request.processing_mode).start_analysis(project, request.processing_mode)
    return build_response(updated).model_dump()


@router.get("/projects/{project_id}/detections", response_model=dict)
def list_detections(project_id: str, review_state: str | None = None) -> dict:
    items = job_repository().list_detections(project_id)
    if review_state:
        items = [item for item in items if item.review_state == review_state]
    return {
        "items": [
            PlayerDetectionResponse(
                detection_id=item.detection_id,
                start_time_seconds=item.start_time_seconds,
                end_time_seconds=item.end_time_seconds,
                team_match_confidence=item.team_match_confidence,
                identity_confidence=item.identity_confidence,
                review_state=item.review_state,
                visual_cues_used=item.visual_cues_used,
            ).model_dump()
            for item in items
        ]
    }

