from __future__ import annotations

from fastapi import APIRouter

from src.api.routes.projects import build_response
from src.api.schemas.detections import ReviewDecisionInput
from src.app.dependencies import project_repository, review_service

router = APIRouter(tags=["reviews"])


@router.post("/projects/{project_id}/detections/{detection_id}/review", response_model=dict)
def review_detection(project_id: str, detection_id: str, request: ReviewDecisionInput) -> dict:
    project = project_repository().get_project(project_id)
    updated = review_service().apply_review(project, detection_id, request.decision, request.reviewer_note)
    return build_response(updated).model_dump()

