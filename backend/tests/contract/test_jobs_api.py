from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import dependencies
from src.app.main import app


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AI_FOCUS_DB_PATH", str(tmp_path / "data" / "app.db"))
    dependencies.clear_caches()
    return TestClient(app)


def test_jobs_list_and_cancel_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(monkeypatch, tmp_path)
    project_id = client.post("/projects", json={"name": "Match"}).json()["project_id"]
    superseded = dependencies.job_service().enqueue(project_id, "sleep_demo")
    dependencies.job_service().repository.mark_failed(superseded.job_id, "old failure")
    job = dependencies.job_service().enqueue(project_id, "sleep_demo")

    listed = client.get(f"/projects/{project_id}/jobs")
    cancelled = client.post(f"/jobs/{job.job_id}/cancel")

    assert listed.status_code == 200
    assert len(listed.json()["jobs"]) == 1
    assert listed.json()["jobs"][0] == {
        "job_id": job.job_id,
        "stage": "sleep_demo",
        "status": "queued",
        "progress_pct": 0.0,
        "progress_message": None,
        "error": None,
        "created_at": job.created_at,
        "started_at": None,
        "finished_at": None,
    }
    assert cancelled.status_code == 200
    assert cancelled.json() == {"job_id": job.job_id, "status": "cancelled"}
