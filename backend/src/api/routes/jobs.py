from __future__ import annotations

from fastapi import APIRouter

from src.app.dependencies import job_service, project_repository
from src.app.errors import AppError


router = APIRouter(tags=["jobs"])


def _job_payload(job) -> dict:
    return {
        "job_id": job.job_id,
        "stage": job.stage,
        "status": job.status,
        "progress_pct": job.progress_pct,
        "progress_message": job.progress_message,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


@router.get("/projects/{project_id}/jobs")
def list_jobs(project_id: str) -> dict:
    try:
        project_repository().get(project_id)
    except KeyError as exc:
        raise AppError("Project not found", status_code=404) from exc
    latest_by_stage = {}
    for job in job_service().repository.list_for_project(project_id):
        latest_by_stage[job.stage] = job
    return {"jobs": [_job_payload(job) for job in latest_by_stage.values()]}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    try:
        job = job_service().cancel(job_id)
    except KeyError as exc:
        raise AppError("Analysis job not found", status_code=404) from exc
    return {"job_id": job.job_id, "status": job.status}
