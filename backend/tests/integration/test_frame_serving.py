from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import dependencies
from src.app.main import app
from tests.fixtures.make_synthetic_match import make_synthetic_match


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe required",
)
def test_attach_proxy_and_serve_real_jpeg(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video_path, _ = make_synthetic_match(tmp_path / "fixture")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", ".local/data")
    monkeypatch.setenv("AI_FOCUS_DB_PATH", ".local/data/app.db")
    monkeypatch.setenv("AI_FOCUS_VIDEO_ROOT", "fixture")
    dependencies.clear_caches()
    client = TestClient(app)
    project_id = client.post("/projects", json={"name": "Synthetic"}).json()["project_id"]

    with video_path.open("rb") as video:
        attached = client.post(
            f"/projects/{project_id}/source",
            files={"file": ("synthetic.mp4", video, "video/mp4")},
        )
    assert attached.status_code == 202, attached.text
    assert Path(attached.json()["source"]["file_path"]).is_absolute()
    proxy_job_id = attached.json()["jobs_queued"][0]["job_id"]
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        job = dependencies.job_repository().get(proxy_job_id)
        if job.status in {"succeeded", "failed"}:
            break
        time.sleep(0.05)

    assert job.status == "succeeded", job.error
    response = client.get(f"/projects/{project_id}/frame", params={"t": 4.2})

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content.startswith(b"\xff\xd8")
