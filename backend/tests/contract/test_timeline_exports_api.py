from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.app import dependencies
from src.app.main import app
from src.domain.models.detection import IdentityCluster, Tracklet
from src.domain.models.project import AnalysisProject
from src.domain.models.selection import AppearanceSegment
from src.domain.models.video import SourceVideo


def _seed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    confirmed: bool,
    with_segments: bool,
) -> tuple[TestClient, str]:
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AI_FOCUS_DB_PATH", str(tmp_path / "data" / "app.db"))
    dependencies.clear_caches()
    project = AnalysisProject(project_id="p1", name="Match", source_id="s1")
    dependencies.project_repository().create(project)
    dependencies.source_repository().insert(
        SourceVideo(
            source_id="s1",
            project_id="p1",
            file_path=str(tmp_path / "match.mp4"),
            duration_s=120.0,
        )
    )
    dependencies.analysis_repository().bulk_upsert_clusters(
        [IdentityCluster("cluster-1", "s1", 2, 15.0)]
    )
    dependencies.analysis_repository().bulk_upsert_tracklets(
        [
            Tracklet("t1", "s1", 5.0, 10.0, 30, cluster_id="cluster-1"),
            Tracklet("t2", "s1", 40.0, 50.0, 60, cluster_id="cluster-1"),
        ]
    )
    if confirmed:
        dependencies.project_repository().set_target_cluster("p1", "cluster-1")
    if with_segments:
        dependencies.selection_repository().replace_segments(
            "p1",
            [
                AppearanceSegment(
                    segment_id="seg-a",
                    project_id="p1",
                    cluster_id="cluster-1",
                    start_ts=3.5,
                    end_ts=11.5,
                    score=8.0,
                    included=True,
                ),
                AppearanceSegment(
                    segment_id="seg-b",
                    project_id="p1",
                    cluster_id="cluster-1",
                    start_ts=38.5,
                    end_ts=51.5,
                    score=13.0,
                    included=True,
                ),
            ],
        )
    return TestClient(app), project.project_id


def test_get_timeline_returns_summary_and_segments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _seed(
        tmp_path, monkeypatch, confirmed=True, with_segments=True
    )
    response = client.get(f"/projects/{project_id}/timeline")
    assert response.status_code == 200
    body = response.json()

    summary = body["summary"]
    assert summary["segment_count"] == 2
    assert summary["included_count"] == 2
    assert summary["total_s"] == pytest.approx(8.0 + 13.0)

    segments = body["segments"]
    assert len(segments) == 2
    for segment in segments:
        assert set(
            ["segment_id", "start_ts", "end_ts", "score", "included", "thumbnail_uri", "preview_clip_uri"]
        ).issubset(segment.keys())
        assert isinstance(segment["included"], bool)
        assert isinstance(segment["thumbnail_uri"], str) and segment["thumbnail_uri"]
        assert isinstance(segment["preview_clip_uri"], str) and segment["preview_clip_uri"]


def test_patch_timeline_toggles_inclusion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _seed(
        tmp_path, monkeypatch, confirmed=True, with_segments=True
    )
    patched = client.patch(
        f"/projects/{project_id}/timeline/seg-a", json={"included": False}
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["segment_id"] == "seg-a"
    assert body["included"] is False

    timeline = client.get(f"/projects/{project_id}/timeline").json()
    assert timeline["summary"]["segment_count"] == 2
    assert timeline["summary"]["included_count"] == 1


def test_post_exports_blocked_when_target_not_confirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _seed(
        tmp_path, monkeypatch, confirmed=False, with_segments=False
    )
    response = client.post(
        f"/projects/{project_id}/exports",
        json={"profile": "short_highlight", "overlay_mode": "none"},
    )
    assert response.status_code == 409
    assert "Confirm your player" in response.json()["detail"]


def test_post_exports_enqueues_job_when_confirmed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _seed(
        tmp_path, monkeypatch, confirmed=True, with_segments=True
    )
    enqueued: list[tuple[str, str, dict]] = []

    class StubJobService:
        def enqueue(self, project_id: str, stage: str, params: dict):
            enqueued.append((project_id, stage, params))
            return SimpleNamespace(job_id="export-job-1")

        def start_next(self):
            return None

    monkeypatch.setattr(dependencies, "job_service", lambda: StubJobService())
    dependencies.export_service.cache_clear()

    response = client.post(
        f"/projects/{project_id}/exports",
        json={"profile": "short_highlight", "overlay_mode": "target_marker"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["job_id"] == "export-job-1"
    assert body["output_id"]

    assert enqueued and enqueued[0][0] == project_id
    assert enqueued[0][1] == "export"
    assert enqueued[0][2]["output_id"] == body["output_id"]

    saved = dependencies.output_repository().get(body["output_id"])
    assert saved.status == "queued"
    assert saved.profile == "short_highlight"
    assert saved.overlay_mode == "target_marker"
    assert saved.segment_ids  # included segments recorded for traceability


def test_get_exports_lists_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _seed(
        tmp_path, monkeypatch, confirmed=True, with_segments=True
    )
    from src.domain.models.output import ReelOutput

    dependencies.output_repository().save(
        ReelOutput(
            output_id="out-1",
            project_id=project_id,
            profile="short_highlight",
            overlay_mode="none",
            status="ready",
            duration_s=21.0,
            segment_ids=["seg-a", "seg-b"],
        )
    )
    response = client.get(f"/projects/{project_id}/exports")
    assert response.status_code == 200
    outputs = response.json()["outputs"]
    assert any(item["output_id"] == "out-1" for item in outputs)
    listed = next(item for item in outputs if item["output_id"] == "out-1")
    assert set(["output_id", "profile", "overlay_mode", "status", "created_at"]).issubset(
        listed.keys()
    )
