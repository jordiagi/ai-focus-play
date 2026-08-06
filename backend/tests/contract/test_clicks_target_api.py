from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.api.routes import clicks as clicks_route
from src.app import dependencies
from src.app.main import app
from src.domain.models.detection import Detection, IdentityCluster, Tracklet
from src.domain.models.pipeline import PipelineJob
from src.domain.models.project import AnalysisProject
from src.domain.models.video import SourceVideo
from src.services.click_service import ClickService
from src.services.pipeline.assemble_candidates_stage import write_candidate_manifest


def _client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, str]:
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AI_FOCUS_DB_PATH", str(tmp_path / "data" / "app.db"))
    dependencies.clear_caches()
    project = AnalysisProject(
        project_id="p1", source_id="s1", status="awaiting_target_selection"
    )
    source = SourceVideo(
        source_id="s1",
        project_id="p1",
        file_path=str(tmp_path / "match.mp4"),
        duration_s=20,
    )
    dependencies.project_repository().create(project)
    dependencies.source_repository().insert(source)
    dependencies.analysis_repository().bulk_upsert_clusters(
        [IdentityCluster("cluster-1", "s1", 2, 8)]
    )
    dependencies.analysis_repository().bulk_upsert_tracklets(
        [
            Tracklet("t1", "s1", 1, 4, 10, cluster_id="cluster-1"),
            Tracklet("t2", "s1", 8, 13, 12, cluster_id="cluster-1"),
        ]
    )
    dependencies.analysis_repository().bulk_insert_detections(
        [Detection("s1", 2.0, 0.4, 0.3, 0.2, 0.4, 0.9, "t1")]
    )
    return TestClient(app), project.project_id


def test_click_routes_return_tracklet_pin_and_no_player_resolutions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        clicks_route,
        "click_service",
        lambda: ClickService(dependencies.database()),
    )

    tracklet = client.post(
        f"/projects/{project_id}/clicks",
        json={"t": 2, "x_norm": 0.5, "y_norm": 0.5, "label": "positive"},
    )
    pinned = client.post(
        f"/projects/{project_id}/clicks",
        json={"t": 18, "x_norm": 0.5, "y_norm": 0.5, "label": "positive"},
    )
    no_player = client.post(
        f"/projects/{project_id}/clicks",
        json={"t": 2, "x_norm": 0.05, "y_norm": 0.05, "label": "positive"},
    )
    listed = client.get(f"/projects/{project_id}/clicks")

    assert tracklet.status_code == 200
    assert tracklet.json()["resolution"] == "tracklet"
    assert tracklet.json()["box"] == {"x": 0.4, "y": 0.3, "w": 0.2, "h": 0.4}
    assert pinned.json()["resolution"] == "pinned"
    assert no_player.json()["resolution"] == "no_player_here"
    assert len(listed.json()["clicks"]) == 3


def test_analyzed_miss_dependency_enqueues_refinement_after_click_is_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    events: list[object] = []

    class StubJobService:
        def enqueue(self, project_id: str, stage: str, params: dict):
            events.append((project_id, stage, params))
            return SimpleNamespace(job_id="sam2-1")

        def start_next(self):
            click = dependencies.selection_repository().list_clicks(project_id)[0]
            events.append((click.status, click.sam2_job_id))

    monkeypatch.setattr(dependencies, "job_service", lambda: StubJobService())
    dependencies.click_service.cache_clear()

    response = client.post(
        f"/projects/{project_id}/clicks",
        json={"t": 2, "x_norm": 0.05, "y_norm": 0.05, "label": "positive"},
    )

    assert response.status_code == 200
    assert response.json()["resolution"] == "sam2_queued"
    assert response.json()["job_id"] == "sam2-1"
    assert events[0][0:2] == (project_id, "sam2_refine")
    assert events[0][2] == {"click_id": response.json()["click_id"]}
    assert events[1] == ("refining", "sam2-1")


def test_click_route_preserves_sam2_queued_response_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(tmp_path, monkeypatch)

    class StubClickService:
        def submit_click(self, *args, **kwargs):
            return {
                "click_id": "click-1",
                "resolution": "sam2_queued",
                "job_id": "job-1",
            }

    monkeypatch.setattr(clicks_route, "click_service", lambda: StubClickService())

    response = client.post(
        f"/projects/{project_id}/clicks",
        json={"t": 2, "x_norm": 0.1, "y_norm": 0.1, "label": "positive"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "click_id": "click-1",
        "resolution": "sam2_queued",
        "job_id": "job-1",
    }


def test_target_confirm_adjust_and_reset_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(tmp_path, monkeypatch)

    confirmed = client.post(
        f"/projects/{project_id}/target", json={"cluster_id": "cluster-1"}
    )
    removed = client.post(
        f"/projects/{project_id}/target/adjust",
        json={"remove_tracklet_ids": ["t2"]},
    )
    removed_tracklet = dependencies.analysis_repository().get_tracklet("t2")
    added = client.post(
        f"/projects/{project_id}/target/adjust",
        json={"add_tracklet_ids": ["t2"]},
    )
    reset = client.delete(f"/projects/{project_id}/target")

    assert confirmed.status_code == 200
    assert confirmed.json()["target_cluster_id"] == "cluster-1"
    assert confirmed.json()["coverage"]["segment_count"] == 2
    assert removed.json()["coverage"]["segment_count"] == 1
    assert removed_tracklet.cluster_id is None
    assert removed_tracklet.cluster_assignment == "user_removed"
    assert added.json()["coverage"]["segment_count"] == 2
    assert reset.status_code == 204
    assert dependencies.project_repository().get(project_id).status == "awaiting_target_selection"


def test_not_them_works_before_confirmation_and_refreshes_candidate_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    write_candidate_manifest(
        dependencies.settings(),
        project_id,
        "cluster-1",
        {
            "cluster_id": "cluster-1",
            "jersey_number": None,
            "jersey_agreement": {"readings": 0, "agrees_with_hint": None},
            "kit_color_name": "blue",
            "screen_time_s": 8,
            "tracklet_count": 2,
            "rep_crop_uri": "/projects/p1/evidence-media/rep.jpg",
            "evidence": [
                {
                    "ts": 2,
                    "thumbnail_uri": "/projects/p1/evidence-media/t1.jpg",
                    "tracklet_id": "t1",
                },
                {
                    "ts": 9,
                    "thumbnail_uri": "/projects/p1/evidence-media/t2.jpg",
                    "tracklet_id": "t2",
                },
            ],
            "timeline_spans": [],
            "rank_score": 8,
        },
    )

    response = client.post(
        f"/projects/{project_id}/target/adjust",
        json={"remove_tracklet_ids": ["t2"]},
    )
    candidate = client.get(
        f"/projects/{project_id}/candidates",
        params={"cluster_id": "cluster-1"},
    ).json()["candidates"][0]

    assert response.status_code == 200
    assert [item["tracklet_id"] for item in candidate["evidence"]] == ["t1"]
    assert candidate["tracklet_count"] == 1
