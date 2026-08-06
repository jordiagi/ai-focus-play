from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import pytest

from src.app.config import Settings
from src.domain.models.project import AnalysisProject
from src.domain.models.selection import UserClick
from src.domain.models.video import SourceVideo
from src.ml.interfaces import DetectionBox, FrameInput
from src.services.pipeline.detect_track_stage import (
    DetectTrackStage,
    TrackedDetection,
)
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository
from tests.fakes.fake_models import FakeDetector
from tests.fixtures.make_synthetic_match import make_synthetic_match


class IdentityTracker:
    def __init__(self) -> None:
        self.ids: dict[str, int] = {}

    def update(
        self, detections: Sequence[DetectionBox]
    ) -> list[TrackedDetection]:
        tracked = []
        for detection in detections:
            identity = detection.identity_id or "unknown"
            tracker_id = self.ids.setdefault(identity, len(self.ids) + 1)
            tracked.append(TrackedDetection(tracker_id, detection))
        return tracked


class FirstDetectionOnlyTracker:
    def update(
        self, detections: Sequence[DetectionBox]
    ) -> list[TrackedDetection]:
        return [TrackedDetection(1, detections[0])] if detections else []


@dataclass
class RecordingContext:
    job_id: str = "detect-job"
    cancelled: bool = False
    stop_after_checkpoints: int | None = None
    updates: list[tuple[float, str, dict | None]] = field(default_factory=list)

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None:
        self.updates.append((progress_pct, message, checkpoint))
        checkpoints = sum(item[2] is not None for item in self.updates)
        if self.stop_after_checkpoints is not None and checkpoints >= self.stop_after_checkpoints:
            self.cancelled = True


class FakeCropWriter:
    def __call__(
        self,
        frame: FrameInput,
        box: DetectionBox,
        path: Path,
    ) -> tuple[float, int]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff\xd8fake-jpeg\xff\xd9")
        return 12.5, round(box.h * int(frame.height or 0))


@pytest.fixture
def stage_fixture(tmp_path: Path):
    video_path, truth_path = make_synthetic_match(tmp_path / "fixture")
    settings = Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "app.db",
        analysis_fps=6.0,
        crop_interval_s=2.0,
    )
    database = Database(settings.db_path)
    project = AnalysisProject(project_id="p1", source_id="s1", status="analyzing")
    source = SourceVideo(
        source_id="s1",
        project_id="p1",
        file_path=str(video_path),
        duration_s=10.0,
        fps=10.0,
        width=640,
        height=360,
    )
    ProjectRepository(database).create(project)
    SourceRepository(database).insert(source)
    return settings, database, project, source, truth_path


def _stage(
    settings: Settings,
    database: Database,
    truth_path: Path,
    *,
    checkpoint_every: int = 1_000,
    frame_streamer=None,
    tracker_factory=IdentityTracker,
) -> DetectTrackStage:
    return DetectTrackStage(
        settings=settings,
        database=database,
        detector=FakeDetector(truth_path),
        tracker_factory=tracker_factory,
        crop_writer=FakeCropWriter(),
        checkpoint_every=checkpoint_every,
        frame_streamer=frame_streamer,
    )


def test_persists_tracklets_and_samples_crops_at_configured_cadence(
    stage_fixture,
) -> None:
    settings, database, project, source, truth_path = stage_fixture

    _stage(settings, database, truth_path).process(
        RecordingContext(), project.project_id, source, checkpoint={}
    )

    repository = AnalysisRepository(database)
    tracklets = repository.list_tracklets(source.source_id)
    assert len(tracklets) == 2
    assert all(tracklet.frame_count == 60 for tracklet in tracklets)
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT tracklet_id, ts, sharpness, bbox_h_px FROM tracklet_crops ORDER BY tracklet_id, ts"
        ).fetchall()
    by_tracklet: dict[str, list[float]] = {}
    for row in rows:
        by_tracklet.setdefault(row["tracklet_id"], []).append(row["ts"])
        assert row["sharpness"] == 12.5
        assert row["bbox_h_px"] == 110
    assert all(len(times) == 5 for times in by_tracklet.values())
    assert all(
        later - earlier >= settings.crop_interval_s - 1e-6
        for times in by_tracklet.values()
        for earlier, later in zip(times, times[1:])
    )


def test_writes_checkpoint_every_thousand_frames(stage_fixture) -> None:
    settings, database, project, source, truth_path = stage_fixture

    def frames(*_: object) -> Iterable[FrameInput]:
        for index in range(1_001):
            yield FrameInput(
                data=b"",
                ts=index / settings.analysis_fps,
                width=640,
                height=360,
            )

    context = RecordingContext()
    _stage(
        settings,
        database,
        truth_path,
        frame_streamer=frames,
    ).process(context, project.project_id, source, checkpoint={})

    checkpoints = [update[2] for update in context.updates if update[2] is not None]
    assert checkpoints[0]["last_ts"] == pytest.approx(999 / settings.analysis_fps)
    assert checkpoints[-1]["last_ts"] == pytest.approx(1_000 / settings.analysis_fps)
    assert len(checkpoints) == 2


def test_resume_replays_warmup_without_duplicate_detections(stage_fixture) -> None:
    settings, database, project, source, truth_path = stage_fixture
    interrupted = RecordingContext(stop_after_checkpoints=1)
    _stage(settings, database, truth_path, checkpoint_every=20).process(
        interrupted, project.project_id, source, checkpoint={}
    )
    checkpoint = next(update[2] for update in interrupted.updates if update[2])

    _stage(settings, database, truth_path, checkpoint_every=20).process(
        RecordingContext(), project.project_id, source, checkpoint=checkpoint
    )

    with database.connect() as connection:
        total = connection.execute(
            "SELECT COUNT(*) FROM detections WHERE source_id = ?", (source.source_id,)
        ).fetchone()[0]
        distinct = connection.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT tracklet_id, ts, x, y, w, h FROM detections
                WHERE source_id = ? GROUP BY tracklet_id, ts, x, y, w, h
            )
            """,
            (source.source_id,),
        ).fetchone()[0]
    assert total == 120
    assert distinct == total
    assert all(tracklet.frame_count == 60 for tracklet in AnalysisRepository(database).list_tracklets(source.source_id))


def test_resume_after_warmup_window_uses_a_new_tracker_id_namespace(
    stage_fixture,
) -> None:
    settings, database, project, source, truth_path = stage_fixture
    interrupted = RecordingContext(stop_after_checkpoints=1)
    _stage(settings, database, truth_path, checkpoint_every=40).process(
        interrupted, project.project_id, source, checkpoint={}
    )
    checkpoint = next(update[2] for update in interrupted.updates if update[2])

    _stage(settings, database, truth_path, checkpoint_every=40).process(
        RecordingContext(), project.project_id, source, checkpoint=checkpoint
    )

    tracklets = AnalysisRepository(database).list_tracklets(source.source_id)
    assert len(tracklets) == 4
    assert len({tracklet.tracklet_id.rsplit("-", maxsplit=2)[-2] for tracklet in tracklets}) == 2
    assert all(tracklet.end_ts - tracklet.start_ts < 7 for tracklet in tracklets)


def test_checkpoint_resolves_pinned_click_when_box_has_been_analyzed(
    stage_fixture,
) -> None:
    settings, database, project, source, truth_path = stage_fixture
    SelectionRepository(database).save_click(
        UserClick(
            click_id="pin-1",
            project_id=project.project_id,
            ts=2.0,
            x_norm=(40 + 20 * 2.0 + 22.5) / 640,
            y_norm=(100 + 55) / 360,
            label="positive",
            status="pinned",
        )
    )

    _stage(settings, database, truth_path, checkpoint_every=20).process(
        RecordingContext(), project.project_id, source, checkpoint={}
    )

    click = SelectionRepository(database).list_clicks(project.project_id)[0]
    assert click.status == "resolved"
    assert click.resolved_tracklet_id is not None


def test_persists_detector_boxes_that_byte_track_does_not_promote(
    stage_fixture,
) -> None:
    settings, database, project, source, truth_path = stage_fixture

    _stage(
        settings,
        database,
        truth_path,
        tracker_factory=FirstDetectionOnlyTracker,
    ).process(RecordingContext(), project.project_id, source, checkpoint={})

    detections = AnalysisRepository(database).detections_in_range(
        source.source_id, 0, source.duration_s or 0
    )
    assert len(detections) == 120
    assert sum(detection.tracklet_id is None for detection in detections) == 60
    assert len(AnalysisRepository(database).list_tracklets(source.source_id)) == 1
