import cv2
import numpy as np
import pytest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.src.api.guards import ReadOnlyAPIMiddleware
from backend.src.app.main import app
from backend.src.storage.repository import match_repo
from backend.src.api.routes.matches import process_uploaded_video_task
from backend.src.config import MEDIA_DIR

@pytest.fixture
def client():
    return TestClient(app)


def test_read_only_middleware_blocks_only_api_mutations():
    guarded_app = FastAPI()
    guarded_app.add_middleware(ReadOnlyAPIMiddleware, enabled=True)

    @guarded_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def endpoint(path: str):
        return {"path": path}

    with TestClient(guarded_app) as guarded_client:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = guarded_client.request(method, "/api/resource")
            assert response.status_code == 403
            assert "read-only" in response.json()["detail"].lower()

        assert guarded_client.get("/api/resource").status_code == 200
        assert guarded_client.post("/media/resource").status_code == 200
        assert guarded_client.post("/docs").status_code == 200


def test_disabled_read_only_middleware_allows_api_mutations():
    writable_app = FastAPI()
    writable_app.add_middleware(ReadOnlyAPIMiddleware, enabled=False)

    @writable_app.post("/api/resource")
    def endpoint():
        return {"created": True}

    with TestClient(writable_app) as writable_client:
        assert writable_client.post("/api/resource").status_code == 200

def _create_dummy_video(path: Path, duration_sec: float = 3.0):
    fps = 30
    w, h = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(path), fourcc, fps, (w, h))
    for _ in range(int(fps * duration_sec)):
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = [45, 120, 45]  # green field
        out.write(frame)
    out.release()

def test_upload_pipeline_success(client, tmp_path: Path):
    """Verifies that an uploaded soccer video processes through CV and reaches ready status (P0-1 & P2-3)."""
    vid_file = tmp_path / "sample_match.mp4"
    _create_dummy_video(vid_file, duration_sec=3.0)

    with open(vid_file, "rb") as f:
        res = client.post(
            "/api/matches/upload",
            files={"file": ("sample_match.mp4", f, "video/mp4")},
            data={"home_team": "Team A", "away_team": "Team B", "date": "Today"}
        )

    assert res.status_code == 200
    match_data = res.json()
    match_id = match_data["id"]
    assert match_data["status"] == "processing"

    # Run processing task synchronously to verify pipeline
    # Resolve against the CONFIGURED media dir, not a hardcoded relative path:
    # the suite now runs against an isolated directory (backend/tests/conftest.py).
    dest_path = MEDIA_DIR / f"{match_id}.mp4"
    process_uploaded_video_task(match_id, dest_path)

    # Fetch updated match
    updated = client.get(f"/api/matches/{match_id}").json()
    assert updated["status"] == "ready"
    assert updated["analysis_mode"] == "heuristic"

    # Highlights and radar frames should exist without PermissionError
    highlights = client.get(f"/api/matches/{match_id}/highlights").json()
    assert isinstance(highlights, list)

    radar = client.get(f"/api/matches/{match_id}/radar").json()
    assert len(radar) > 0

    # Cleanup match and verify secure file deletion (P2-6)
    del_res = client.delete(f"/api/matches/{match_id}")
    assert del_res.status_code == 200
    assert not dest_path.exists()

def test_upload_rejects_invalid_extensions(client, tmp_path: Path):
    fake_file = tmp_path / "script.html"
    fake_file.write_text("<h1>Not a video</h1>")

    with open(fake_file, "rb") as f:
        res = client.post(
            "/api/matches/upload",
            files={"file": ("script.html", f, "text/html")}
        )
    assert res.status_code == 415

def test_upload_rejects_corrupt_video(client, tmp_path: Path):
    bad_vid = tmp_path / "corrupt.mp4"
    bad_vid.write_bytes(b"0000notarealmp4video")

    with open(bad_vid, "rb") as f:
        res = client.post(
            "/api/matches/upload",
            files={"file": ("corrupt.mp4", f, "video/mp4")}
        )
    assert res.status_code == 400
