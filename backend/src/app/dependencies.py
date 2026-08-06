from __future__ import annotations

from functools import lru_cache

from src.app.config import Settings, get_settings
from src.services.artifact_service import ArtifactService
from src.services.cleanup_service import CleanupService
from src.services.click_service import ClickService
from src.services.evidence_artifact_service import EvidenceArtifactService
from src.services.frame_service import FrameService
from src.services.job_service import JobService
from src.services.identity_service import IdentityService
from src.services.export_service import ExportService
from src.services.source_catalog_service import SourceCatalogService
from src.services.timeline_service import TimelineService
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.job_repository import JobRepository
from src.storage.output_repository import OutputRepository
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository


@lru_cache
def settings() -> Settings:
    return get_settings()


@lru_cache
def database() -> Database:
    return Database(settings().db_path)


@lru_cache
def project_repository() -> ProjectRepository:
    return ProjectRepository(database())


@lru_cache
def source_repository() -> SourceRepository:
    return SourceRepository(database())


@lru_cache
def analysis_repository() -> AnalysisRepository:
    return AnalysisRepository(database())


@lru_cache
def selection_repository() -> SelectionRepository:
    return SelectionRepository(database())


@lru_cache
def output_repository() -> OutputRepository:
    return OutputRepository(database())


@lru_cache
def job_repository() -> JobRepository:
    return JobRepository(database())


@lru_cache
def job_service() -> JobService:
    return JobService(database(), settings())


@lru_cache
def artifact_service() -> ArtifactService:
    return ArtifactService(settings())


@lru_cache
def evidence_artifact_service() -> EvidenceArtifactService:
    return EvidenceArtifactService(artifact_service(), settings())


@lru_cache
def frame_service() -> FrameService:
    return FrameService(artifact_service(), settings())


@lru_cache
def source_catalog_service() -> SourceCatalogService:
    return SourceCatalogService(settings().video_root)


@lru_cache
def cleanup_service() -> CleanupService:
    return CleanupService(settings())


@lru_cache
def click_service() -> ClickService:
    jobs = job_service()

    def enqueue_refinement(click):
        job = jobs.enqueue(
            click.project_id,
            "sam2_refine",
            {"click_id": click.click_id},
        )
        return {"resolution": "sam2_queued", "job_id": job.job_id}

    return ClickService(
        database(),
        miss_resolver=enqueue_refinement,
        job_starter=jobs.start_next,
    )


@lru_cache
def identity_service() -> IdentityService:
    return IdentityService(database())


@lru_cache
def timeline_service() -> TimelineService:
    return TimelineService(
        database(),
        settings=settings(),
        artifacts=artifact_service(),
        evidence=evidence_artifact_service(),
    )


@lru_cache
def export_service() -> ExportService:
    def enqueue_export(project_id: str, output_id: str) -> str:
        jobs = job_service()
        job = jobs.enqueue(project_id, "export", {"output_id": output_id})
        jobs.start_next()
        return job.job_id

    return ExportService(
        outputs=output_repository(),
        selection=selection_repository(),
        projects=project_repository(),
        enqueue_export=enqueue_export,
    )


def clear_caches() -> None:
    for dependency in (
        export_service,
        timeline_service,
        identity_service,
        click_service,
        cleanup_service,
        source_catalog_service,
        evidence_artifact_service,
        frame_service,
        artifact_service,
        output_repository,
        job_service,
        job_repository,
        selection_repository,
        analysis_repository,
        source_repository,
        project_repository,
        database,
        settings,
    ):
        dependency.cache_clear()
