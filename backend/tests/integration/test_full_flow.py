from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import pytest
from fastapi.testclient import TestClient

from src.app import dependencies
from src.app.config import Settings
from src.app.main import app
from src.domain.models.project import AnalysisProject
from src.domain.models.video import SourceVideo
from src.ml.interfaces import CropInput, DetectionBox
from src.services.export_service import ExportService
from src.services.pipeline.assemble_candidates_stage import AssembleCandidatesStage
from src.services.pipeline.detect_track_stage import DetectTrackStage, TrackedDetection
from src.services.pipeline.embed_cluster_stage import EmbedClusterStage
from src.services.pipeline.export_stage import run_export_stage
from src.services.pipeline.jersey_ocr_stage import JerseyOCRStage
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.output_repository import OutputRepository
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository
from tests.fakes.fake_models import FakeDetector, FakeEmbedder, FakeOCR
from tests.fixtures.make_synthetic_match import make_synthetic_match


@dataclass
class RecordingContext:
    job_id: str = "pipeline-job"
    cancelled: bool = False
    updates: list[tuple[float, str, dict | None]] = field(default_factory=list)

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None:
        self.updates.append((progress_pct, message, checkpoint))


class IdentityTracker:
    def __init__(self) -> None:
        self.ids: dict[str, int] = {}

    def update(self, detections: Sequence[DetectionBox]) -> list[TrackedDetection]:
        return [
            TrackedDetection(
                self.ids.setdefault(detection.identity_id or "unknown", len(self.ids) + 1),
                detection,
            )
            for detection in detections
        ]


def _write_fake_crop(path: Path, box: DetectionBox, frame_height: int | None) -> tuple[float, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xd8fake\xff\xd9")
    return 10.0, round(box.h * int(frame_height or 0))


def _fake_evidence(project_id: str, source_path: Path, cluster_id: str, crops) -> list[dict]:
    del source_path
    return [
        {
            "ts": crop.ts,
            "thumbnail_uri": f"/projects/{project_id}/evidence-media/{cluster_id}-{index}.jpg",
            "clip_uri": f"/projects/{project_id}/evidence-media/{cluster_id}-{index}.mp4",
            "tracklet_id": crop.tracklet_id,
        }
        for index, crop in enumerate(crops, start=1)
    ]


def _run_analysis_chain(
    settings: Settings, database: Database, source: SourceVideo, truth_path: Path
) -> None:
    DetectTrackStage(
        settings=settings,
        database=database,
        detector=FakeDetector(truth_path),
        tracker_factory=IdentityTracker,
        crop_writer=lambda frame, box, path: _write_fake_crop(path, box, frame.height),
    ).process(RecordingContext(), source.project_id, source, checkpoint={})

    identities = {"000001": "home-8", "000002": "away-11"}
    EmbedClusterStage(
        settings=settings,
        database=database,
        embedder=FakeEmbedder(),
        crop_loader=lambda crop: CropInput(
            data=Path(crop.crop_path).read_bytes(),
            identity_id=identities[crop.tracklet_id.rsplit("-", maxsplit=1)[-1]],
        ),
        kit_color_extractor=lambda crop: (
            ("red", "0,255,255") if crop.tracklet_id.endswith("000001") else ("blue", "120,255,255")
        ),
    ).process(RecordingContext(), source.project_id, source, checkpoint={})

    numbers = {"000001": "8", "000002": "11"}
    JerseyOCRStage(
        settings=settings,
        database=database,
        recognizer=FakeOCR(),
        crop_loader=lambda crop: CropInput(
            data=Path(crop.crop_path).read_bytes(),
            number=numbers[crop.tracklet_id.rsplit("-", maxsplit=1)[-1]],
        ),
    ).process(RecordingContext(), source.project_id, source, checkpoint={})

    AssembleCandidatesStage(
        settings=settings,
        database=database,
        evidence_builder=_fake_evidence,
    ).process(RecordingContext(), source.project_id, source)


def test_full_flow_attach_to_export_renders_real_mp4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg is required to render the reel")

    video_path, truth_path = make_synthetic_match(tmp_path / "fixture")
    settings = Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "app.db",
        analysis_fps=6.0,
        crop_interval_s=1.0,
    )
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(settings.data_dir))
    monkeypatch.setenv("AI_FOCUS_DB_PATH", str(settings.db_path))
    dependencies.clear_caches()
    database = Database(settings.db_path)

    project = AnalysisProject(project_id="p1", source_id="s1", status="analyzing")
    source = SourceVideo(
        source_id="s1",
        project_id="p1",
        file_path=str(video_path),
        duration_s=10,
        fps=10,
        width=640,
        height=360,
    )
    ProjectRepository(database).create(project)
    SourceRepository(database).insert(source)

    _run_analysis_chain(settings, database, source, truth_path)

    client = TestClient(app)

    # 1. Candidates are available; pick the first as the target.
    candidates = client.get("/projects/p1/candidates").json()["candidates"]
    assert candidates
    cluster_id = candidates[0]["cluster_id"]

    # 2. Confirm the target -> builds coverage segments synchronously.
    confirm = client.post("/projects/p1/target", json={"cluster_id": cluster_id})
    assert confirm.status_code == 200
    assert confirm.json()["coverage"]["segment_count"] >= 1

    # 3. Timeline exposes the segments with media URIs and per-segment tracklets.
    timeline = client.get("/projects/p1/timeline").json()
    assert timeline["summary"]["segment_count"] >= 1
    first_segment = timeline["segments"][0]
    assert first_segment["thumbnail_uri"] and first_segment["preview_clip_uri"]
    assert first_segment["tracklet_ids"]

    # 4. Exclude then re-include a segment via PATCH; included_count tracks it.
    seg_id = first_segment["segment_id"]
    client.patch(f"/projects/p1/timeline/{seg_id}", json={"included": False})
    excluded = client.get("/projects/p1/timeline").json()["summary"]
    assert excluded["included_count"] == timeline["summary"]["included_count"] - 1
    client.patch(f"/projects/p1/timeline/{seg_id}", json={"included": True})

    # 5. Create an export (bypassing the subprocess enqueue), then render it directly.
    confirmed_project = ProjectRepository(database).get("p1")
    enqueued: list[tuple[str, str]] = []
    service = ExportService(
        outputs=OutputRepository(database),
        selection=SelectionRepository(database),
        projects=ProjectRepository(database),
        enqueue_export=lambda pid, oid: (enqueued.append((pid, oid)), "job-x")[1],
    )
    output, job_id = service.create(confirmed_project, "full_appearances", "none")
    assert job_id == "job-x"
    assert enqueued == [("p1", output.output_id)]
    assert output.status == "queued"
    assert output.segment_ids

    run_export_stage(RecordingContext(), {"output_id": output.output_id})

    rendered = OutputRepository(database).get(output.output_id)
    assert rendered.status == "ready"
    assert rendered.duration_s and rendered.duration_s > 0
    assert rendered.file_path is not None
    reel = Path(rendered.file_path)
    assert reel.is_file() and reel.stat().st_size > 0

    # 6. Blocked before confirmation: a fresh project cannot export.
    ProjectRepository(database).create(AnalysisProject(project_id="p2", source_id="s1"))
    blocked = client.post("/projects/p2/exports", json={"profile": "short_highlight", "overlay_mode": "none"})
    assert blocked.status_code == 409
    assert "Confirm your player" in blocked.json()["detail"]
