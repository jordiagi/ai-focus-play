from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import dependencies
from src.app.config import Settings
from src.app.main import app
from src.domain.models.project import AnalysisProject
from src.services.job_service import JobService
from src.storage.db import Database
from src.storage.project_repository import ProjectRepository


def _wait_for(service: JobService, job_id: str, predicate, timeout: float = 8.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = service.repository.get(job_id)
        if predicate(job):
            return job
        time.sleep(0.03)
    raise AssertionError(f"job {job_id} did not reach expected state: {job}")


def _setup(tmp_path: Path) -> tuple[Database, Settings]:
    settings = Settings(data_dir=tmp_path / "data", db_path=tmp_path / "app.db")
    settings.ensure_directories()
    database = Database(settings.db_path)
    ProjectRepository(database).create(AnalysisProject(project_id="p1"))
    return database, settings


def test_sleep_demo_live_progress_and_cancel(tmp_path: Path) -> None:
    database, settings = _setup(tmp_path)
    service = JobService(database, settings, recover_running=False)
    job = service.enqueue(
        "p1", "sleep_demo", {"duration_s": 1.2, "steps": 12}
    )

    service.start_next()
    running = _wait_for(service, job.job_id, lambda item: item.progress_pct > 0)
    assert "steps" in (running.progress_message or "")
    service.cancel(job.job_id)
    cancelled = _wait_for(
        service, job.job_id, lambda item: item.status == "cancelled"
    )

    assert 0 < cancelled.progress_pct < 100
    assert cancelled.checkpoint["completed_steps"] >= 1


def test_killed_stage_resumes_from_checkpoint(tmp_path: Path) -> None:
    database, settings = _setup(tmp_path)
    service = JobService(database, settings, recover_running=False)
    job = service.enqueue(
        "p1", "sleep_demo", {"duration_s": 1.5, "steps": 15}
    )
    service.claim_next()
    env = {
        **os.environ,
        "AI_FOCUS_DB_PATH": str(settings.db_path),
        "AI_FOCUS_DATA_DIR": str(settings.data_dir),
    }
    child = subprocess.Popen(
        [sys.executable, "-m", "src.workers.run_stage", "--job-id", job.job_id],
        cwd=Path(__file__).parents[2],
        env=env,
    )
    progressed = _wait_for(service, job.job_id, lambda item: item.progress_pct >= 20)
    completed_before_kill = progressed.checkpoint["completed_steps"]
    child.kill()
    child.wait(timeout=3)

    restarted = JobService(database, settings, recover_running=True)
    assert restarted.repository.get(job.job_id).status == "queued"
    restarted.start_next()
    finished = _wait_for(
        restarted, job.job_id, lambda item: item.status == "succeeded"
    )

    assert completed_before_kill >= 3
    assert finished.progress_pct == 100
    assert finished.checkpoint["completed_steps"] == 15


def test_worker_stops_for_resume_when_parent_process_is_gone(tmp_path: Path) -> None:
    database, settings = _setup(tmp_path)
    service = JobService(database, settings, recover_running=False)
    job = service.enqueue(
        "p1", "sleep_demo", {"duration_s": 0.2, "steps": 2}
    )
    service.claim_next()
    env = {
        **os.environ,
        "AI_FOCUS_DB_PATH": str(settings.db_path),
        "AI_FOCUS_DATA_DIR": str(settings.data_dir),
        "AI_FOCUS_PARENT_PID": "99999999",
    }

    orphan = subprocess.run(
        [sys.executable, "-m", "src.workers.run_stage", "--job-id", job.job_id],
        cwd=Path(__file__).parents[2],
        env=env,
        timeout=3,
    )

    assert orphan.returncode == 3
    assert service.repository.get(job.job_id).status == "running"
    restarted = JobService(database, settings, recover_running=True)
    assert restarted.repository.get(job.job_id).status == "queued"


def test_app_startup_recovers_and_restarts_interrupted_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, settings = _setup(tmp_path)
    service = JobService(database, settings, recover_running=False)
    job = service.enqueue(
        "p1", "sleep_demo", {"duration_s": 0.2, "steps": 2}
    )
    service.claim_next()
    monkeypatch.setenv("AI_FOCUS_DB_PATH", str(settings.db_path))
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(settings.data_dir))
    dependencies.clear_caches()

    with TestClient(app):
        finished = _wait_for(
            dependencies.job_service(),
            job.job_id,
            lambda item: item.status == "succeeded",
        )

    assert finished.progress_pct == 100


def test_worker_uses_server_resolved_paths_for_relative_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        data_dir=Path(".local/data"),
        db_path=Path(".local/data/app.db"),
        video_root=Path("video"),
    )
    database = Database(settings.db_path)
    ProjectRepository(database).create(AnalysisProject(project_id="p1"))
    service = JobService(database, settings, recover_running=False)
    job = service.enqueue(
        "p1", "sleep_demo", {"duration_s": 0.1, "steps": 2}
    )

    service.start_next()
    finished = _wait_for(
        service,
        job.job_id,
        lambda item: item.status in {"succeeded", "failed"},
    )

    assert finished.status == "succeeded", finished.error
