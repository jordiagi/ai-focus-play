import io
import json
import os
import tracemalloc
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from backend.src.app.main import app
from backend.src.config import MEDIA_DIR
from backend.src.domain.models.match import AnalyticsData, Highlight, Match, TeamStats
from backend.src.storage.repository import match_repo
from backend.src.api.routes import matches as matches_route
from backend.src.services.pipeline.video_processor import VideoProcessor


@pytest.fixture
def client():
    return TestClient(app)


def _make_match(match_id: str) -> Match:
    m = Match(
        id=match_id,
        title="Export Test Match",
        home_team="Home",
        away_team="Away",
        date="Today",
        video_url=f"/media/{match_id}.mp4",
        status="ready",
    )
    match_repo.save_match(m)
    return m


def test_export_never_substitutes_missing_clip_and_records_manifest(client):
    """A missing clip must be omitted (with a manifest note), never replaced by
    the full match video or any other file (defect 6)."""
    match_id = f"export-test-{uuid.uuid4().hex[:8]}"
    _make_match(match_id)

    # A distinct "full match" video that must never leak into the export as a
    # substitute for a missing highlight clip.
    full_video = MEDIA_DIR / f"{match_id}_full.mp4"
    full_video.write_bytes(b"FULL-MATCH-VIDEO-BYTES" * 1000)

    # A genuine per-highlight clip, byte-distinct from the full video.
    real_clip = MEDIA_DIR / f"clip_{match_id}_real.mp4"
    real_clip.write_bytes(b"REAL-HIGHLIGHT-CLIP-BYTES" * 10)

    h_ok = Highlight(
        match_id=match_id, title="Real Clip", event_type="goal",
        start_time=1.0, end_time=5.0, clip_url=f"/media/{real_clip.name}",
    )
    h_missing = Highlight(
        match_id=match_id, title="Missing Clip", event_type="shot",
        start_time=10.0, end_time=15.0,
        clip_url=f"/media/clip_{match_id}_does_not_exist.mp4",
    )
    match_repo.add_highlight(h_ok, internal=True)
    match_repo.add_highlight(h_missing, internal=True)

    try:
        res = client.get(f"/api/matches/{match_id}/highlights/export")
        assert res.status_code == 200
        # A truly streamed response never precomputes Content-Length.
        assert "content-length" not in {k.lower() for k in res.headers.keys()}

        full_bytes = full_video.read_bytes()
        with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
            names = zf.namelist()
            for name in names:
                if name == "manifest.json":
                    continue
                assert zf.read(name) != full_bytes, (
                    f"zip member {name!r} is byte-identical to the full match video"
                )
            manifest = json.loads(zf.read("manifest.json"))

        by_title = {e["title"]: e for e in manifest}
        assert by_title["Real Clip"]["status"] == "included"
        assert by_title["Real Clip"]["file"] is not None
        assert by_title["Missing Clip"]["status"] == "omitted"
        assert by_title["Missing Clip"]["file"] is None
        assert by_title["Missing Clip"].get("reason")
    finally:
        match_repo.delete_match(match_id)
        full_video.unlink(missing_ok=True)
        real_clip.unlink(missing_ok=True)


def test_export_returns_streaming_response(client):
    match_id = f"export-type-{uuid.uuid4().hex[:8]}"
    _make_match(match_id)
    clip = MEDIA_DIR / f"clip_{match_id}.mp4"
    clip.write_bytes(b"clip-bytes")
    match_repo.add_highlight(
        Highlight(match_id=match_id, title="Clip", event_type="goal",
                  start_time=0.0, end_time=5.0, clip_url=f"/media/{clip.name}"),
        internal=True,
    )
    try:
        response = matches_route.export_highlights_zip(match_id)
        assert isinstance(response, StreamingResponse)
    finally:
        match_repo.delete_match(match_id)
        clip.unlink(missing_ok=True)


def test_zip_streaming_helper_has_bounded_peak_memory():
    """The archive must be streamed off disk in fixed-size chunks, not held
    resident as a single in-memory buffer (defect 6)."""
    big_file = MEDIA_DIR / f"bounded-mem-{uuid.uuid4().hex[:8]}.zip"
    payload_size = 6 * 1024 * 1024
    big_file.write_bytes(os.urandom(payload_size))

    tracemalloc.start()
    try:
        total = 0
        for chunk in matches_route._iter_zip_file_and_cleanup(big_file, chunk_size=64 * 1024):
            total += len(chunk)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert total == payload_size
    assert peak < payload_size / 2, (
        f"peak traced memory ({peak} bytes) is too close to the payload size "
        f"({payload_size} bytes) -- looks like the whole file was buffered"
    )
    assert not big_file.exists(), "streaming helper must delete the temp file once fully sent"


def _stub_process_video(*, video_path, progress_callback=None):
    return [], [], [], AnalyticsData(home_stats=TeamStats(), away_stats=TeamStats())


def test_no_engine_meta_reports_demo_low(monkeypatch):
    """Catches: relabelling every run (including synthetic fallback) with a fixed
    'heuristic'/'medium' string. When the engine reports nothing, the honest
    label is demo/low (defect 4)."""
    match_id = f"label-demo-{uuid.uuid4().hex[:8]}"
    _make_match(match_id)
    monkeypatch.setattr(matches_route.cv_engine, "process_video", _stub_process_video)
    monkeypatch.delattr(matches_route.cv_engine, "last_run_meta", raising=False)
    monkeypatch.setattr(VideoProcessor, "get_video_metadata", staticmethod(lambda p: {"duration": 90.0}))
    monkeypatch.setattr(VideoProcessor, "extract_thumbnail", staticmethod(lambda *a, **k: False))

    try:
        matches_route.process_uploaded_video_task(match_id, Path("/nonexistent/video.mp4"))
        updated = match_repo.get_match(match_id)
        assert updated.status == "ready"
        assert updated.analysis_mode == "demo"
        assert updated.analysis_confidence == "low"
    finally:
        match_repo.delete_match(match_id)


def test_engine_reported_mode_is_not_relabelled_demo(monkeypatch):
    """A genuine engine-reported mode must survive untouched -- the fix must not
    flatten every run (fallback or real) to the same literal (defect 4)."""
    match_id = f"label-ml-{uuid.uuid4().hex[:8]}"
    _make_match(match_id)
    monkeypatch.setattr(matches_route.cv_engine, "process_video", _stub_process_video)
    monkeypatch.setattr(matches_route.cv_engine, "last_run_meta",
                         {"mode": "ml", "confidence": "high"}, raising=False)
    monkeypatch.setattr(VideoProcessor, "get_video_metadata", staticmethod(lambda p: {"duration": 90.0}))
    monkeypatch.setattr(VideoProcessor, "extract_thumbnail", staticmethod(lambda *a, **k: False))

    try:
        matches_route.process_uploaded_video_task(match_id, Path("/nonexistent/video.mp4"))
        updated = match_repo.get_match(match_id)
        assert updated.status == "ready"
        assert updated.analysis_mode == "ml"
        assert updated.analysis_confidence == "high"
    finally:
        match_repo.delete_match(match_id)
