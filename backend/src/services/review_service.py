from __future__ import annotations

from uuid import uuid4

from src.app.errors import AppError
from src.app.logging import log_event
from src.domain.models.project import AnalysisProject, utcnow
from src.domain.models.review import ReviewDecision
from src.services.detection_service import DetectionService
from src.storage.job_repository import JobRepository
from src.storage.project_repository import ProjectRepository


class ReviewService:
    def __init__(
        self,
        project_repository: ProjectRepository,
        job_repository: JobRepository,
        detection_service: DetectionService,
    ) -> None:
        self.project_repository = project_repository
        self.job_repository = job_repository
        self.detection_service = detection_service

    def apply_review(self, project: AnalysisProject, detection_id: str, decision: str, reviewer_note: str) -> AnalysisProject:
        detection = self.job_repository.get_detection(detection_id)
        if detection.review_state not in {"needs_review", "auto_accepted", "approved"}:
            raise AppError("Detection cannot be reviewed in its current state", status_code=409)
        detection.review_state = {"approve": "approved", "reject": "rejected", "defer": "needs_review"}[decision]
        self.job_repository.save_detection(detection)
        review = ReviewDecision(
            review_decision_id=str(uuid4()),
            detection_id=detection_id,
            decision=decision,
            reviewed_at=utcnow(),
            reviewer_note=reviewer_note,
        )
        self.job_repository.save_review(review)
        detections = self.job_repository.list_detections(project.project_id)
        project.verification_score = self.detection_service.verification_score(detections)
        project.status = "ready_for_export" if project.verification_score >= project.verification_threshold else "review_required"
        project.updated_at = utcnow()
        self.project_repository.save_project(project)
        log_event("review_applied", project_id=project.project_id, detection_id=detection_id, decision=decision)
        return project

