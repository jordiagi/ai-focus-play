from __future__ import annotations

from pathlib import Path

import pytest

from src.app.config import Settings
from src.domain.models.detection import IdentityCluster, Tracklet
from src.domain.models.project import AnalysisProject
from src.domain.models.video import SourceVideo
from src.services.timeline_service import TimelineService
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository


def _setup(tmp_path: Path, tracklets: list[Tracklet], duration_s: float = 120.0) -> tuple[TimelineService, Database]:
    settings = Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "app.db",
    )
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    database = Database(settings.db_path)
    ProjectRepository(database).create(
        AnalysisProject(project_id="p1", name="Match", source_id="s1")
    )
    SourceRepository(database).insert(
        SourceVideo(
            source_id="s1",
            project_id="p1",
            file_path=str(tmp_path / "match.mp4"),
            duration_s=duration_s,
        )
    )
    analysis = AnalysisRepository(database)
    analysis.bulk_upsert_clusters([IdentityCluster("cluster-1", "s1", len(tracklets), 0.0)])
    analysis.bulk_upsert_tracklets(tracklets)
    return TimelineService(database), database


def _segments(database: Database) -> list:
    return SelectionRepository(database).list_segments("p1")


def test_merges_tracklets_when_gap_below_two_seconds(tmp_path: Path) -> None:
    # gap 10.0 -> 11.0 is 1.0s (< 2.0) => merge; both long enough to survive drop.
    service, database = _setup(
        tmp_path,
        [
            Tracklet("t1", "s1", 5.0, 10.0, 30, cluster_id="cluster-1"),
            Tracklet("t2", "s1", 11.0, 16.0, 30, cluster_id="cluster-1"),
        ],
    )
    service.rebuild("p1", "cluster-1")
    segments = _segments(database)
    assert len(segments) == 1
    # merged raw span [5,16] padded +/-1.5 => [3.5, 17.5]
    assert segments[0].start_ts == pytest.approx(3.5)
    assert segments[0].end_ts == pytest.approx(17.5)


def test_does_not_merge_when_gap_exceeds_padding(tmp_path: Path) -> None:
    # gap 10.0 -> 14.0 is 4.0s: no raw merge (>= 2.0) and, after +/-1.5 padding,
    # padded edges [.., 11.5] and [12.5, ..] still do not touch => two segments.
    service, database = _setup(
        tmp_path,
        [
            Tracklet("t1", "s1", 5.0, 10.0, 30, cluster_id="cluster-1"),
            Tracklet("t2", "s1", 14.0, 20.0, 36, cluster_id="cluster-1"),
        ],
    )
    service.rebuild("p1", "cluster-1")
    segments = _segments(database)
    assert len(segments) == 2


def test_drops_tracklet_with_raw_duration_below_1_5s(tmp_path: Path) -> None:
    # t2 raw duration is 1.0s (< 1.5) and isolated => dropped entirely.
    service, database = _setup(
        tmp_path,
        [
            Tracklet("t1", "s1", 5.0, 10.0, 30, cluster_id="cluster-1"),
            Tracklet("t2", "s1", 40.0, 41.0, 6, cluster_id="cluster-1"),
        ],
    )
    service.rebuild("p1", "cluster-1")
    segments = _segments(database)
    assert len(segments) == 1
    assert segments[0].start_ts == pytest.approx(3.5)
    assert segments[0].end_ts == pytest.approx(11.5)


def test_pads_each_segment_and_clamps_to_bounds(tmp_path: Path) -> None:
    # Near t=0 the low pad clamps to 0.0; near duration the high pad clamps to duration.
    service, database = _setup(
        tmp_path,
        [
            Tracklet("t1", "s1", 0.5, 3.0, 20, cluster_id="cluster-1"),
            Tracklet("t2", "s1", 100.0, 119.0, 90, cluster_id="cluster-1"),
        ],
        duration_s=120.0,
    )
    service.rebuild("p1", "cluster-1")
    segments = sorted(_segments(database), key=lambda s: s.start_ts)
    assert len(segments) == 2
    assert segments[0].start_ts == pytest.approx(0.0)  # 0.5 - 1.5 clamped to 0
    assert segments[0].end_ts == pytest.approx(4.5)
    assert segments[1].start_ts == pytest.approx(98.5)
    assert segments[1].end_ts == pytest.approx(120.0)  # 119 + 1.5 clamped to duration


def test_padding_induced_overlap_is_remerged(tmp_path: Path) -> None:
    # raw gap 10.0 -> 12.5 is 2.5s (no raw merge), but padding (+/-1.5) makes them
    # [3.5,11.5] and [11.0,19.5] which overlap => single merged segment.
    service, database = _setup(
        tmp_path,
        [
            Tracklet("t1", "s1", 5.0, 10.0, 30, cluster_id="cluster-1"),
            Tracklet("t2", "s1", 12.5, 18.0, 30, cluster_id="cluster-1"),
        ],
    )
    service.rebuild("p1", "cluster-1")
    segments = _segments(database)
    assert len(segments) == 1
    assert segments[0].start_ts == pytest.approx(3.5)
    assert segments[0].end_ts == pytest.approx(19.5)


def test_excludes_user_removed_tracklets(tmp_path: Path) -> None:
    service, database = _setup(
        tmp_path,
        [
            Tracklet("t1", "s1", 5.0, 10.0, 30, cluster_id="cluster-1"),
            Tracklet(
                "t2",
                "s1",
                40.0,
                46.0,
                30,
                cluster_id="cluster-1",
                cluster_assignment="user_removed",
            ),
        ],
    )
    service.rebuild("p1", "cluster-1")
    segments = _segments(database)
    assert len(segments) == 1
    assert segments[0].start_ts == pytest.approx(3.5)


def test_score_reflects_segment_duration(tmp_path: Path) -> None:
    service, database = _setup(
        tmp_path,
        [
            Tracklet("t1", "s1", 5.0, 8.0, 18, cluster_id="cluster-1"),
            Tracklet("t2", "s1", 40.0, 60.0, 120, cluster_id="cluster-1"),
        ],
    )
    service.rebuild("p1", "cluster-1")
    segments = sorted(_segments(database), key=lambda s: s.start_ts)
    # score == padded segment duration; longer coverage => higher score.
    assert segments[0].score == pytest.approx(segments[0].end_ts - segments[0].start_ts)
    assert segments[1].score > segments[0].score


def test_segment_ids_are_deterministic_across_rebuilds(tmp_path: Path) -> None:
    tracklets = [
        Tracklet("t1", "s1", 5.0, 10.0, 30, cluster_id="cluster-1"),
        Tracklet("t2", "s1", 40.0, 50.0, 60, cluster_id="cluster-1"),
    ]
    service, database = _setup(tmp_path, tracklets)
    service.rebuild("p1", "cluster-1")
    first = {s.segment_id for s in _segments(database)}
    service.rebuild("p1", "cluster-1")
    second = {s.segment_id for s in _segments(database)}
    assert first == second
    assert len(first) == 2


def test_coverage_summary_totals_and_gaps(tmp_path: Path) -> None:
    service, database = _setup(
        tmp_path,
        [
            Tracklet("t1", "s1", 5.0, 10.0, 30, cluster_id="cluster-1"),
            Tracklet("t2", "s1", 40.0, 50.0, 60, cluster_id="cluster-1"),
        ],
        duration_s=120.0,
    )
    coverage = service.rebuild("p1", "cluster-1")
    assert coverage["segment_count"] == 2
    segments = sorted(_segments(database), key=lambda s: s.start_ts)
    expected_total = sum(s.end_ts - s.start_ts for s in segments)
    assert coverage["total_s"] == pytest.approx(expected_total)
    assert coverage["gaps"], "expected gaps between/around segments"
