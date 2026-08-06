from __future__ import annotations

from pathlib import Path

from src.app.config import Settings
from src.domain.models.project import AnalysisProject
from src.services.job_service import JobService
from src.storage.db import Database
from src.storage.project_repository import ProjectRepository


def _service(tmp_path: Path) -> JobService:
    database = Database(tmp_path / "app.db")
    ProjectRepository(database).create(AnalysisProject(project_id="p1"))
    return JobService(
        database,
        Settings(data_dir=tmp_path / "data", db_path=tmp_path / "app.db"),
        recover_running=False,
    )


def test_enqueue_and_claim_allows_only_one_running_job(tmp_path: Path) -> None:
    service = _service(tmp_path)
    first = service.enqueue("p1", "sleep_demo", {"duration_s": 0.1})
    second = service.enqueue("p1", "proxy")

    claimed = service.claim_next()

    assert claimed.job_id == first.job_id
    assert claimed.status == "running"
    assert service.claim_next() is None
    service.repository.mark_succeeded(first.job_id)
    assert service.claim_next().job_id == second.job_id


def test_checkpoint_round_trip_and_cancel_preserve_progress(tmp_path: Path) -> None:
    service = _service(tmp_path)
    job = service.enqueue("p1", "sleep_demo")
    service.claim_next()

    service.repository.update_progress(
        job.job_id,
        progress_pct=40,
        progress_message="Demonstrating background work — 4 of 10 steps",
        checkpoint={"completed_steps": 4},
    )
    cancelled = service.cancel(job.job_id)

    assert cancelled.status == "cancelled"
    assert cancelled.progress_pct == 40
    assert cancelled.checkpoint == {"completed_steps": 4}


def test_recovery_requeues_jobs_left_running(tmp_path: Path) -> None:
    service = _service(tmp_path)
    job = service.enqueue("p1", "sleep_demo")
    service.claim_next()
    service.repository.update_progress(
        job.job_id,
        progress_pct=30,
        progress_message="Demonstrating background work — 3 of 10 steps",
        checkpoint={"completed_steps": 3},
    )

    recovered = service.recover_interrupted()

    assert [item.job_id for item in recovered] == [job.job_id]
    stored = service.repository.get(job.job_id)
    assert stored.status == "queued"
    assert stored.checkpoint == {"completed_steps": 3}
