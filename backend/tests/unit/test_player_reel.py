import io
import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.src.app.main import app
from backend.src.config import MEDIA_DIR
from backend.src.domain.models.match import Highlight, Match, Event
from backend.src.storage.repository import match_repo
from backend.src.services.pipeline.video_processor import VideoProcessor


@pytest.fixture
def client():
    return TestClient(app)


def _make_match(match_id: str) -> Match:
    m = Match(
        id=match_id,
        title="Player Reel Test Match",
        home_team="Arlington",
        away_team="Opponent",
        date="2026-09-27",
        video_url=f"/media/{match_id}_full.mp4",
        status="ready",
    )
    match_repo.save_match(m)
    return m


def test_player_reel_not_found(client):
    res = client.get("/api/matches/non-existent-match-id/players/8/reel")
    assert res.status_code == 404
    assert "Match not found" in res.json()["detail"]


def test_player_reel_no_moments(client):
    match_id = f"reel-test-{uuid.uuid4().hex[:8]}"
    _make_match(match_id)
    res = client.get(f"/api/matches/{match_id}/players/99/reel")
    assert res.status_code == 404
    assert "No plays or moments found for Jersey #99" in res.json()["detail"]


def test_player_reel_success_with_clips(client, monkeypatch):
    match_id = f"reel-test-{uuid.uuid4().hex[:8]}"
    _make_match(match_id)

    clip1 = MEDIA_DIR / f"clip_{match_id}_1.mp4"
    clip1.write_bytes(b"CLIP1-DATA")
    clip2 = MEDIA_DIR / f"clip_{match_id}_2.mp4"
    clip2.write_bytes(b"CLIP2-DATA")

    h1 = Highlight(
        match_id=match_id,
        title="Pass",
        event_type="pass",
        start_time=10.0,
        end_time=15.0,
        player_jersey="8",
        clip_url=f"/media/{clip1.name}",
    )
    h2 = Highlight(
        match_id=match_id,
        title="Shot",
        event_type="shot",
        start_time=20.0,
        end_time=25.0,
        player_jersey="8",
        clip_url=f"/media/{clip2.name}",
    )
    match_repo.add_highlight(h1, internal=True)
    match_repo.add_highlight(h2, internal=True)

    reel_file = MEDIA_DIR / f"reel_{match_id}_jersey_8.mp4"

    # Mock concat_clips to write simulated stitched mp4 bytes
    def mock_concat(paths, output_path):
        output_path.write_bytes(b"STITCHED-REEL-DATA")
        return True

    monkeypatch.setattr(VideoProcessor, "concat_clips", mock_concat)

    try:
        res = client.get(f"/api/matches/{match_id}/players/8/reel")
        assert res.status_code == 200
        assert res.headers["content-type"] == "video/mp4"
        assert "Arlington_Jersey_8_Reel.mp4" in res.headers.get("content-disposition", "")
        assert res.content == b"STITCHED-REEL-DATA"
        assert reel_file.exists()
    finally:
        clip1.unlink(missing_ok=True)
        clip2.unlink(missing_ok=True)
        reel_file.unlink(missing_ok=True)


def test_player_reel_cached_file_reused(client):
    match_id = f"reel-test-{uuid.uuid4().hex[:8]}"
    _make_match(match_id)

    h1 = Highlight(
        match_id=match_id,
        title="Goal",
        event_type="goal",
        start_time=5.0,
        end_time=10.0,
        player_jersey="10",
        clip_url="/media/some_clip.mp4",
    )
    match_repo.add_highlight(h1, internal=True)

    reel_file = MEDIA_DIR / f"reel_{match_id}_jersey_10.mp4"
    reel_file.write_bytes(b"ALREADY-CACHED-REEL")

    try:
        res = client.get(f"/api/matches/{match_id}/players/10/reel")
        assert res.status_code == 200
        assert res.content == b"ALREADY-CACHED-REEL"
    finally:
        reel_file.unlink(missing_ok=True)


def test_concat_clips_single_and_empty(tmp_path):
    assert VideoProcessor.concat_clips([], tmp_path / "out.mp4") is False

    single_in = tmp_path / "single.mp4"
    single_in.write_bytes(b"SINGLE-CLIP")
    single_out = tmp_path / "single_out.mp4"
    assert VideoProcessor.concat_clips([single_in], single_out) is True
    assert single_out.read_bytes() == b"SINGLE-CLIP"
