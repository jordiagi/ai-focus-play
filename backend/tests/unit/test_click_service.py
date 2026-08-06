from __future__ import annotations

from pathlib import Path

from src.domain.models.detection import Detection, IdentityCluster, Tracklet
from src.domain.models.pipeline import PipelineJob
from src.domain.models.project import AnalysisProject
from src.domain.models.video import SourceVideo
from src.services.click_service import ClickService
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.job_repository import JobRepository
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository


def _setup(tmp_path: Path) -> tuple[Database, SourceVideo]:
    database = Database(tmp_path / "app.db")
    source = SourceVideo(
        source_id="s1",
        project_id="p1",
        file_path=str(tmp_path / "match.mp4"),
        duration_s=20,
    )
    ProjectRepository(database).create(
        AnalysisProject(project_id="p1", source_id=source.source_id)
    )
    SourceRepository(database).insert(source)
    AnalysisRepository(database).bulk_upsert_clusters(
        [IdentityCluster("cluster-1", source.source_id, 2, 8)]
    )
    AnalysisRepository(database).bulk_upsert_tracklets(
        [
            Tracklet("far", source.source_id, 4, 6, 5, cluster_id="cluster-1"),
            Tracklet("near", source.source_id, 4, 6, 5, cluster_id="cluster-1"),
        ]
    )
    return database, source


def test_hit_testing_uses_half_second_window_and_nearest_box_on_overlap(
    tmp_path: Path,
) -> None:
    database, source = _setup(tmp_path)
    AnalysisRepository(database).bulk_insert_detections(
        [
            Detection(source.source_id, 5.4, 0.1, 0.1, 0.8, 0.8, 0.9, "far"),
            Detection(source.source_id, 5.4, 0.42, 0.42, 0.2, 0.2, 0.9, "near"),
        ]
    )

    result = ClickService(database).submit_click(
        "p1", t=5.0, x_norm=0.53, y_norm=0.53, label="positive"
    )

    assert result["resolution"] == "tracklet"
    assert result["tracklet_id"] == "near"
    assert result["cluster_id"] == "cluster-1"
    assert SelectionRepository(database).list_clicks("p1")[0].status == "resolved"


def test_unanalyzed_miss_is_pinned_without_calling_escalation(tmp_path: Path) -> None:
    database, _ = _setup(tmp_path)
    called = False

    def escalate(click):
        nonlocal called
        called = True
        return {"resolution": "sam2_queued", "job_id": "refine"}

    result = ClickService(database, miss_resolver=escalate).submit_click(
        "p1", t=12, x_norm=0.5, y_norm=0.5, label="positive"
    )

    assert result["resolution"] == "pinned"
    assert "we'll match this player" in result["message"]
    assert called is False


def test_analyzed_miss_uses_escalation_decision(tmp_path: Path) -> None:
    database, _ = _setup(tmp_path)
    repository = JobRepository(database)
    repository.create(
        PipelineJob(job_id="detect", project_id="p1", stage="detect_track")
    )
    repository.claim_next()
    repository.update_progress(
        "detect",
        progress_pct=50,
        progress_message="Watching the match",
        checkpoint={"last_ts": 10.0},
    )

    worker_observations: list[tuple[str, str | None]] = []

    def start_worker() -> None:
        click = SelectionRepository(database).list_clicks("p1")[0]
        worker_observations.append((click.status, click.sam2_job_id))

    result = ClickService(
        database,
        miss_resolver=lambda click: {
            "resolution": "sam2_queued",
            "job_id": "refine",
        },
        job_starter=start_worker,
    ).submit_click("p1", t=8, x_norm=0.05, y_norm=0.05, label="positive")

    assert result["resolution"] == "sam2_queued"
    assert result["job_id"] == "refine"
    click = SelectionRepository(database).list_clicks("p1")[0]
    assert click.status == "refining"
    assert click.sam2_job_id == "refine"
    assert worker_observations == [("refining", "refine")]


def test_negative_click_is_persisted_with_its_resolved_tracklet(tmp_path: Path) -> None:
    database, source = _setup(tmp_path)
    AnalysisRepository(database).bulk_insert_detections(
        [Detection(source.source_id, 3.0, 0.4, 0.4, 0.2, 0.2, 0.9, "near")]
    )

    ClickService(database).submit_click(
        "p1", t=3, x_norm=0.5, y_norm=0.5, label="negative"
    )

    click = SelectionRepository(database).list_clicks("p1")[0]
    assert click.label == "negative"
    assert click.resolved_tracklet_id == "near"
