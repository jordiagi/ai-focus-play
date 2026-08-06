from __future__ import annotations

from src.app.logging import log_event
from src.domain.models.project import AnalysisProject, utcnow
from src.services.detection_service import DetectionService
from src.storage.job_repository import JobRepository
from src.storage.project_repository import ProjectRepository
from src.workers.base import WorkerRunner


class AnalysisService:
    def __init__(
        self,
        project_repository: ProjectRepository,
        job_repository: JobRepository,
        detection_service: DetectionService,
        runner: WorkerRunner,
    ) -> None:
        self.project_repository = project_repository
        self.job_repository = job_repository
        self.detection_service = detection_service
        self.runner = runner

    def start_analysis(self, project: AnalysisProject, processing_mode: str) -> AnalysisProject:
        project.processing_mode = processing_mode
        project.status = "analyzing"
        project.updated_at = utcnow()
        self.project_repository.save_project(project)
        self.runner.submit("python3 analyze.py")
        detections = self.detection_service.generate_candidate_detections(project)
        for detection in detections:
            self.job_repository.save_detection(detection)
        project.verification_score = self.detection_service.verification_score(detections)
        project.status = "review_required" if any(d.review_state == "needs_review" for d in detections) else "ready_for_export"
        project.updated_at = utcnow()
        self.project_repository.save_project(project)
        log_event("analysis_started", project_id=project.project_id, processing_mode=processing_mode)
        return project
