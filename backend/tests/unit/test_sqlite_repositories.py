from pathlib import Path

import struct

from src.domain.models.detection import (
    Detection,
    IdentityCluster,
    Tracklet,
    TrackletCrop,
    TrackletEmbedding,
)
from src.domain.models.output import ReelOutput
from src.domain.models.project import AnalysisProject
from src.domain.models.selection import AppearanceSegment, UserClick
from src.domain.models.video import SourceVideo
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.output_repository import OutputRepository
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository


def test_source_analysis_selection_and_output_round_trips(tmp_path: Path) -> None:
    database = Database(tmp_path / "app.db")
    ProjectRepository(database).create(AnalysisProject(project_id="p1"))
    SourceRepository(database).save(
        SourceVideo(
            source_id="s1",
            project_id="p1",
            file_path="/tmp/match.mp4",
            duration_s=10.0,
        )
    )
    analysis = AnalysisRepository(database)
    analysis.bulk_upsert_tracklets(
        [Tracklet("t1", "s1", 1.0, 2.0, 2, avg_conf=0.9)]
    )
    analysis.bulk_insert_detections(
        [
            Detection("s1", 1.0, 0.1, 0.2, 0.1, 0.3, 0.9, "t1"),
            Detection("s1", 2.0, 0.2, 0.2, 0.1, 0.3, 0.8, "t1"),
        ]
    )

    selection = SelectionRepository(database)
    selection.save_click(UserClick("c1", "p1", 1.0, 0.15, 0.3, "positive", "resolved", "t1"))
    selection.replace_segments(
        "p1", [AppearanceSegment("a1", "p1", "cluster-1", 0.5, 2.5, 0.8)]
    )
    outputs = OutputRepository(database)
    outputs.save(ReelOutput("o1", "p1", "full_appearances", "none", segment_ids=["a1"]))

    assert SourceRepository(database).get_for_project("p1").source_id == "s1"
    assert [item.tracklet_id for item in analysis.detections_near("s1", 1.1)] == ["t1"]
    assert selection.list_clicks("p1")[0].resolved_tracklet_id == "t1"
    assert selection.list_segments("p1")[0].included is True
    assert outputs.get("o1").segment_ids == ["a1"]


def test_discontinuous_tracklet_repair_preserves_crops_and_click_resolution(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "app.db")
    projects = ProjectRepository(database)
    projects.create(AnalysisProject(project_id="p1"))
    SourceRepository(database).save(
        SourceVideo(source_id="s1", project_id="p1", file_path="/tmp/match.mp4")
    )
    analysis = AnalysisRepository(database)
    analysis.bulk_upsert_tracklets(
        [Tracklet("reused", "s1", 0.0, 5.2, 4, avg_conf=0.85, cluster_id="c1")]
    )
    analysis.bulk_insert_detections(
        [
            Detection("s1", 0.0, 0.1, 0.2, 0.1, 0.3, 0.9, "reused"),
            Detection("s1", 0.2, 0.1, 0.2, 0.1, 0.3, 0.8, "reused"),
            Detection("s1", 5.0, 0.6, 0.2, 0.1, 0.3, 0.9, "reused"),
            Detection("s1", 5.2, 0.6, 0.2, 0.1, 0.3, 0.8, "reused"),
        ]
    )
    analysis.bulk_insert_crops(
        [
            TrackletCrop("crop-early", "reused", 0.0, "/tmp/early.jpg"),
            TrackletCrop("crop-late", "reused", 5.0, "/tmp/late.jpg"),
        ]
    )
    analysis.bulk_upsert_embeddings(
        [TrackletEmbedding("reused", "fake", 2, struct.pack("<2f", 1, 0), 2)]
    )
    analysis.bulk_upsert_clusters([IdentityCluster("c1", "s1", 1, 5.2)])
    selection = SelectionRepository(database)
    selection.save_click(
        UserClick("click-late", "p1", 5.1, 0.65, 0.3, "positive", "resolved", "reused")
    )
    projects.set_target_cluster("p1", "c1")
    selection.replace_segments(
        "p1", [AppearanceSegment("segment-1", "p1", "c1", 0, 5.2)]
    )

    repaired = analysis.repair_discontinuous_tracklets("s1", "p1")

    tracklets = analysis.list_tracklets("s1")
    assert repaired == 2
    assert len(tracklets) == 2
    assert all(
        round(tracklet.end_ts - tracklet.start_ts, 6) == 0.2
        for tracklet in tracklets
    )
    assert {crop.tracklet_id for tracklet in tracklets for crop in analysis.list_crops(tracklet.tracklet_id)} == {
        tracklet.tracklet_id for tracklet in tracklets
    }
    click = selection.list_clicks("p1")[0]
    assert click.resolved_tracklet_id.endswith("0000005000")
    assert analysis.list_clusters("s1") == []
    assert analysis.list_embeddings("s1") == []
    assert selection.list_segments("p1") == []
    assert projects.get("p1").target_cluster_id is None
