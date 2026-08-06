from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.app import dependencies
from src.app.main import app
from src.domain.models.detection import IdentityCluster, Tracklet, TrackletCrop
from src.domain.models.project import AnalysisProject
from src.domain.models.pipeline import PipelineJob
from src.domain.models.video import SourceVideo
from src.services.pipeline.assemble_candidates_stage import write_candidate_manifest
from src.storage.job_repository import JobRepository


def _client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[TestClient, str]:
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AI_FOCUS_DB_PATH", str(tmp_path / "data" / "app.db"))
    dependencies.clear_caches()
    project = AnalysisProject(project_id="p1", name="Match")
    dependencies.project_repository().create(project)
    write_candidate_manifest(
        dependencies.settings(),
        project.project_id,
        "cluster-1",
        {
            "cluster_id": "cluster-1",
            "jersey_number": None,
            "jersey_agreement": {"readings": 0, "agrees_with_hint": None},
            "kit_color_name": "blue",
            "screen_time_s": 14.5,
            "tracklet_count": 2,
            "rep_crop_uri": "/projects/p1/evidence-media/cluster-1-rep.jpg",
            "evidence": [
                {
                    "ts": 3.0,
                    "thumbnail_uri": "/projects/p1/evidence-media/cluster-1-1.jpg",
                    "clip_uri": "/projects/p1/evidence-media/cluster-1-1.mp4",
                    "tracklet_id": "t1",
                }
            ],
            "timeline_spans": [{"start_ts": 1.0, "end_ts": 8.0}],
            "rank_score": 14.5,
        },
    )
    return TestClient(app), project.project_id


def test_candidates_response_matches_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(tmp_path, monkeypatch)

    response = client.get(f"/projects/{project_id}/candidates")

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate == {
        "cluster_id": "cluster-1",
        "jersey_number": None,
        "jersey_agreement": {"readings": 0, "agrees_with_hint": None},
        "kit_color_name": "blue",
        "screen_time_s": 14.5,
        "tracklet_count": 2,
        "rep_crop_uri": "/projects/p1/evidence-media/cluster-1-rep.jpg",
        "evidence": [
            {
                "ts": 3.0,
                "thumbnail_uri": "/projects/p1/evidence-media/cluster-1-1.jpg",
                "clip_uri": "/projects/p1/evidence-media/cluster-1-1.mp4",
                "tracklet_id": "t1",
            }
        ],
        "timeline_spans": [{"start_ts": 1.0, "end_ts": 8.0}],
    }


def test_candidates_can_filter_to_one_cluster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(tmp_path, monkeypatch)

    response = client.get(
        f"/projects/{project_id}/candidates", params={"cluster_id": "missing"}
    )

    assert response.status_code == 200
    assert response.json() == {"candidates": []}


def test_candidates_anchor_evidence_to_the_clicked_tracklet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    source = SourceVideo(
        source_id="source-1",
        project_id=project_id,
        file_path=str(tmp_path / "match.mp4"),
    )
    dependencies.source_repository().insert(source)
    dependencies.project_repository().set_source(project_id, source.source_id)
    dependencies.analysis_repository().bulk_upsert_clusters(
        [
            IdentityCluster(
                cluster_id="cluster-1",
                source_id=source.source_id,
                tracklet_count=2,
                screen_time_s=12.0,
            )
        ]
    )
    dependencies.analysis_repository().bulk_upsert_tracklets(
        [
            Tracklet(
                "t1",
                source.source_id,
                2.0,
                4.0,
                3,
                kit_color_name="blue",
                cluster_id="cluster-1",
            ),
            Tracklet(
                "t2",
                source.source_id,
                40.0,
                44.0,
                5,
                kit_color_name="green",
                cluster_id="cluster-1",
            ),
        ]
    )
    early_crop = tmp_path / "early.jpg"
    clicked_crop = tmp_path / "clicked.jpg"
    early_crop.write_bytes(b"early crop")
    clicked_crop.write_bytes(b"clicked crop")
    dependencies.analysis_repository().bulk_insert_crops(
        [
            TrackletCrop("crop-t2-early", "t2", 40.0, str(early_crop)),
            TrackletCrop("crop-t2-clicked", "t2", 43.0, str(clicked_crop)),
        ]
    )

    response = client.get(
        f"/projects/{project_id}/candidates",
        params={
            "cluster_id": "cluster-1",
            "anchor_tracklet_id": "t2",
            "anchor_ts": 42.5,
        },
    )

    assert response.status_code == 200
    evidence = response.json()["candidates"][0]["evidence"]
    assert evidence[0]["tracklet_id"] == "t2"
    assert evidence[0]["ts"] == 43.0
    assert len(evidence) == 1
    assert response.json()["candidates"][0]["ambiguous"] is True
    assert client.get(evidence[0]["thumbnail_uri"]).status_code == 200


def test_jersey_hint_reranks_candidates_and_can_be_cleared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    write_candidate_manifest(
        dependencies.settings(),
        project_id,
        "cluster-2",
        {
            "cluster_id": "cluster-2",
            "jersey_number": "8",
            "jersey_agreement": {"readings": 3, "agrees_with_hint": None},
            "kit_color_name": "red",
            "screen_time_s": 12.0,
            "tracklet_count": 1,
            "rep_crop_uri": "/projects/p1/evidence-media/cluster-2-rep.jpg",
            "evidence": [],
            "timeline_spans": [],
            "rank_score": 12.0,
        },
    )

    response = client.put(
        f"/projects/{project_id}/jersey-hint", json={"jersey_hint": "8"}
    )
    candidates = client.get(f"/projects/{project_id}/candidates").json()[
        "candidates"
    ]

    assert response.status_code == 200
    assert response.json() == {"jersey_hint": "8"}
    assert candidates[0]["cluster_id"] == "cluster-2"
    assert candidates[0]["jersey_agreement"] == {
        "readings": 3,
        "agrees_with_hint": True,
    }
    assert client.put(
        f"/projects/{project_id}/jersey-hint", json={"jersey_hint": None}
    ).json() == {"jersey_hint": None}


def test_project_reports_when_completed_ocr_found_no_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, project_id = _client(tmp_path, monkeypatch)
    repository = JobRepository(dependencies.database())
    repository.create(
        PipelineJob(job_id="ocr-job", project_id=project_id, stage="jersey_ocr")
    )
    repository.claim_next()
    repository.update_progress(
        "ocr-job",
        progress_pct=100,
        progress_message="Reading jersey numbers",
        checkpoint={"done_tracklet_ids": [], "no_readable_numbers": True},
    )
    repository.mark_succeeded("ocr-job")

    response = client.get(f"/projects/{project_id}")

    assert response.status_code == 200
    assert response.json()["analysis"]["no_readable_jersey_numbers"] is True
