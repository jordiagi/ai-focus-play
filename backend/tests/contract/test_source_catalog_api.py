import shutil
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.app import dependencies
from src.api.routes import sources as source_routes
from src.app.main import app
from tests.fixtures.make_synthetic_match import make_synthetic_match


@dataclass
class _QueuedJob:
    job_id: str
    stage: str


class _FakeJobService:
    def enqueue_chain(self, project_id: str, stages: list[str]) -> list[_QueuedJob]:
        return [_QueuedJob(f"{project_id}-{stage}", stage) for stage in stages]

    def start_next(self) -> None:
        return None


def _reset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AI_FOCUS_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("AI_FOCUS_VIDEO_ROOT", str(tmp_path / "video"))
    dependencies.clear_caches()


def test_local_sources_endpoint_lists_video_folder_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _reset(monkeypatch, tmp_path)
    (tmp_path / "video").mkdir()
    (tmp_path / "video" / "match.mp4").write_text("video")
    client = TestClient(app)

    response = client.get("/sources/local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["display_name"] == "match"
    assert payload["items"][0]["relative_path"] == "match.mp4"


def test_source_selection_rejects_outside_local_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _reset(monkeypatch, tmp_path)
    (tmp_path / "video").mkdir()
    client = TestClient(app)
    project_id = client.post("/projects", json={}).json()["project_id"]

    response = client.post(
        f"/projects/{project_id}/source",
        json={"source_reference": "../outside.mp4"},
    )

    assert response.status_code == 400
    assert "video folder" in response.json()["detail"]


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe required",
)
def test_source_upload_accepts_multipart_video(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset(monkeypatch, tmp_path)
    video_path, _ = make_synthetic_match(tmp_path / "fixture")
    monkeypatch.setattr(source_routes, "job_service", lambda: _FakeJobService())
    client = TestClient(app)
    project_id = client.post("/projects", json={}).json()["project_id"]

    with video_path.open("rb") as video:
        response = client.post(
            f"/projects/{project_id}/source",
            files={"file": ("match.mp4", video, "video/mp4")},
        )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["source"]["original_filename"] == "match.mp4"
    assert Path(payload["source"]["file_path"]).is_absolute()
    assert payload["source"]["duration_s"] == pytest.approx(10.0)
    assert [job["stage"] for job in payload["jobs_queued"]] == source_routes.PIPELINE_STAGES


def test_pipeline_force_reruns_a_succeeded_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _reset(monkeypatch, tmp_path)
    service = _FakeJobService()
    monkeypatch.setattr(source_routes, "job_service", lambda: service)
    monkeypatch.setattr(
        source_routes,
        "job_repository",
        lambda: SimpleNamespace(
            list_for_project=lambda _: [
                SimpleNamespace(stage="jersey_ocr", status="succeeded")
            ]
        ),
    )
    client = TestClient(app)
    project_id = client.post("/projects", json={}).json()["project_id"]

    response = client.post(
        f"/projects/{project_id}/pipeline/run",
        json={"stages": ["jersey_ocr"], "force": True},
    )

    assert response.status_code == 202
    assert response.json()["jobs_queued"] == [
        {"job_id": f"{project_id}-jersey_ocr", "stage": "jersey_ocr"}
    ]
