from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import dependencies
from src.app.main import app
from src.domain.models.detection import Detection, Tracklet
from src.domain.models.pipeline import PipelineJob
from src.domain.models.project import AnalysisProject
from src.domain.models.video import SourceVideo


def _client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[TestClient, str]:
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AI_FOCUS_DB_PATH", str(tmp_path / "data" / "app.db"))
    dependencies.clear_caches()
    project = AnalysisProject(project_id="p1", name="Match", source_id="s1")
    dependencies.project_repository().create(project)
    dependencies.source_repository().save(
        SourceVideo(
            source_id="s1",
            project_id="p1",
            file_path=str(tmp_path / "match.mp4"),
            duration_s=10.0,
            proxy_status="pending",
        )
    )
    return TestClient(app), project.project_id


def test_frame_returns_normative_proxy_pending_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(monkeypatch, tmp_path)

    response = client.get(f"/projects/{project_id}/frame", params={"t": 2.0})

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "We're still getting the video ready — try again in a moment."
    )


def test_frame_detections_are_empty_before_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(monkeypatch, tmp_path)

    response = client.get(
        f"/projects/{project_id}/frame-detections", params={"t": 2.0}
    )

    assert response.status_code == 200
    assert response.json() == {"ts_actual": 2.0, "analyzed": False, "boxes": []}


def test_frame_detections_return_boxes_from_nearest_sampled_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(monkeypatch, tmp_path)
    dependencies.analysis_repository().bulk_upsert_tracklets(
        [
            Tracklet(
                tracklet_id="track-1",
                source_id="s1",
                start_ts=2.0,
                end_ts=2.0,
                frame_count=1,
                avg_conf=0.95,
            )
        ]
    )
    dependencies.analysis_repository().bulk_insert_detections(
        [
            Detection(
                source_id="s1",
                tracklet_id="track-1",
                ts=2.0,
                x=0.2,
                y=0.3,
                w=0.1,
                h=0.25,
                conf=0.95,
            )
        ]
    )

    response = client.get(
        f"/projects/{project_id}/frame-detections", params={"t": 2.2}
    )

    assert response.status_code == 200
    assert response.json() == {
        "ts_actual": 2.0,
        "analyzed": True,
        "boxes": [
            {
                "tracklet_id": "track-1",
                "cluster_id": None,
                "x": 0.2,
                "y": 0.3,
                "w": 0.1,
                "h": 0.25,
                "is_target": False,
            }
        ],
    }


def test_completed_detection_job_marks_empty_region_analyzed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(monkeypatch, tmp_path)
    dependencies.job_repository().create(
        PipelineJob(
            job_id="detect-1",
            project_id=project_id,
            stage="detect_track",
            status="succeeded",
            progress_pct=100,
        )
    )

    response = client.get(
        f"/projects/{project_id}/frame-detections", params={"t": 9.0}
    )

    assert response.json() == {"ts_actual": 9.0, "analyzed": True, "boxes": []}
