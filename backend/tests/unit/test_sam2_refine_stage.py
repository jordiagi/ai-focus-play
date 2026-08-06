from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PIL import Image

from src.app.config import Settings
from src.domain.models.detection import Detection, IdentityCluster, Tracklet
from src.domain.models.project import AnalysisProject
from src.domain.models.selection import UserClick
from src.domain.models.video import SourceVideo
from src.ml.interfaces import FrameInput
from src.services.pipeline.sam2_refine_stage import Sam2RefineStage
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository
from tests.fakes.fake_models import FakeMaskPropagator


@dataclass
class RecordingContext:
    job_id: str = "sam2-job"
    cancelled: bool = False
    updates: list[tuple[float, str, dict | None]] = field(default_factory=list)

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None:
        self.updates.append((progress_pct, message, checkpoint))


class RecordingFrameLoader:
    def __init__(self, timestamps: list[float]) -> None:
        self.timestamps = timestamps
        self.calls: list[tuple[Path, float, float, float, Path]] = []

    def __call__(
        self,
        proxy_path: Path,
        start_ts: float,
        end_ts: float,
        fps: float,
        workspace: Path,
    ) -> list[FrameInput]:
        self.calls.append((proxy_path, start_ts, end_ts, fps, workspace))
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "temporary-frame.jpg").write_bytes(b"frame")
        return [
            FrameInput(
                data=Image.new("RGB", (160, 90), "green"),
                ts=timestamp,
                width=160,
                height=90,
            )
            for timestamp in self.timestamps
        ]


class FailingPropagator:
    def propagate(self, frames, seed_index, point_norm):
        del frames, seed_index, point_norm
        raise RuntimeError("mask failure")


def _setup(tmp_path: Path) -> tuple[Settings, Database, SourceVideo]:
    settings = Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "app.db",
        analysis_fps=2,
        sam2_window_s=4,
    )
    database = Database(settings.db_path)
    proxy_path = tmp_path / "proxy.mp4"
    proxy_path.write_bytes(b"proxy")
    source = SourceVideo(
        source_id="s1",
        project_id="p1",
        file_path=str(tmp_path / "match.mp4"),
        duration_s=10,
        width=160,
        height=90,
        proxy_path=str(proxy_path),
        proxy_status="ready",
    )
    ProjectRepository(database).create(
        AnalysisProject(
            project_id="p1",
            source_id=source.source_id,
            target_cluster_id="target",
            status="target_confirmed",
        )
    )
    SourceRepository(database).insert(source)
    AnalysisRepository(database).bulk_upsert_clusters(
        [IdentityCluster("target", source.source_id, 0, 0, status="confirmed")]
    )
    SelectionRepository(database).save_click(
        UserClick(
            click_id="click-1",
            project_id="p1",
            ts=1,
            x_norm=0.25,
            y_norm=0.45,
            label="positive",
            status="refining",
            sam2_job_id="sam2-job",
        )
    )
    return settings, database, source


def test_iou_voting_assigns_tracklet_and_mints_only_missing_detections(
    tmp_path: Path,
) -> None:
    settings, database, source = _setup(tmp_path)
    analysis = AnalysisRepository(database)
    analysis.bulk_upsert_tracklets(
        [Tracklet("existing", source.source_id, 0.5, 4.0, 2)]
    )
    analysis.bulk_insert_detections(
        [
            Detection(source.source_id, 0.5, 0.2, 0.3, 0.1, 0.3, 0.9, "existing"),
            Detection(source.source_id, 1.0, 0.2, 0.3, 0.1, 0.3, 0.9, "existing"),
        ]
    )
    loader = RecordingFrameLoader([0.5, 1.0, 1.5])
    propagator = FakeMaskPropagator(
        boxes=[
            (0.2, 0.3, 0.1, 0.3),
            (0.2, 0.3, 0.1, 0.3),
            (0.4, 0.2, 0.12, 0.35),
        ]
    )
    context = RecordingContext()

    Sam2RefineStage(
        settings=settings,
        database=database,
        propagator=propagator,
        frame_loader=loader,
    ).process(context, "p1", source, params={"click_id": "click-1"})

    assert loader.calls[0][1:4] == (0.0, 5.0, 2)
    existing = analysis.get_tracklet("existing")
    assert existing.cluster_id == "target"
    assert existing.cluster_assignment == "user_click"
    synthetic = [
        tracklet
        for tracklet in analysis.list_tracklets(source.source_id)
        if tracklet.synthetic
    ]
    assert len(synthetic) == 1
    assert synthetic[0].cluster_id == "target"
    assert synthetic[0].start_ts == 1.5
    synthetic_detections = [
        item
        for item in analysis.detections_near(source.source_id, 1.5, 0.01)
        if item.tracklet_id == synthetic[0].tracklet_id
    ]
    assert len(synthetic_detections) == 1
    click = SelectionRepository(database).get_click("click-1")
    assert click.status == "resolved"
    assert click.resolved_tracklet_id == "existing"
    # New Phase-9 segmentation: the existing appearance and the gap-filled
    # synthetic tracklet merge into a single covered stretch.
    assert len(SelectionRepository(database).list_segments("p1")) == 1
    assert not loader.calls[0][4].exists()
    assert context.updates[-1][0] == 100


def test_no_masks_marks_click_no_player_and_cleans_workspace(tmp_path: Path) -> None:
    settings, database, source = _setup(tmp_path)
    loader = RecordingFrameLoader([0.5, 1.0, 1.5])

    Sam2RefineStage(
        settings=settings,
        database=database,
        propagator=FakeMaskPropagator(boxes=[None, None, None]),
        frame_loader=loader,
    ).process(RecordingContext(), "p1", source, params={"click_id": "click-1"})

    click = SelectionRepository(database).get_click("click-1")
    assert click.status == "no_player"
    assert click.resolved_tracklet_id is None
    assert not loader.calls[0][4].exists()


def test_workspace_is_cleaned_when_propagation_fails(tmp_path: Path) -> None:
    settings, database, source = _setup(tmp_path)
    loader = RecordingFrameLoader([0.5, 1.0])

    with pytest.raises(RuntimeError, match="mask failure"):
        Sam2RefineStage(
            settings=settings,
            database=database,
            propagator=FailingPropagator(),
            frame_loader=loader,
        ).process(
            RecordingContext(),
            "p1",
            source,
            params={"click_id": "click-1"},
        )

    assert not loader.calls[0][4].exists()
