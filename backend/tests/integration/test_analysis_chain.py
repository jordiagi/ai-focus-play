from __future__ import annotations

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
from src.services.pipeline.assemble_candidates_stage import AssembleCandidatesStage
from src.services.pipeline.detect_track_stage import DetectTrackStage, TrackedDetection
from src.services.pipeline.embed_cluster_stage import EmbedClusterStage
from src.services.pipeline.jersey_ocr_stage import JerseyOCRStage
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.project_repository import ProjectRepository
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

    def update(
        self, detections: Sequence[DetectionBox]
    ) -> list[TrackedDetection]:
        return [
            TrackedDetection(
                self.ids.setdefault(
                    detection.identity_id or "unknown", len(self.ids) + 1
                ),
                detection,
            )
            for detection in detections
        ]


def test_full_fake_analysis_chain_produces_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    project = AnalysisProject(
        project_id="p1", source_id="s1", status="analyzing"
    )
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

    DetectTrackStage(
        settings=settings,
        database=database,
        detector=FakeDetector(truth_path),
        tracker_factory=IdentityTracker,
        crop_writer=lambda frame, box, path: _write_fake_crop(path, box, frame.height),
    ).process(RecordingContext(), project.project_id, source, checkpoint={})

    identities = {
        "000001": "home-8",
        "000002": "away-11",
    }
    EmbedClusterStage(
        settings=settings,
        database=database,
        embedder=FakeEmbedder(),
        crop_loader=lambda crop: CropInput(
            data=Path(crop.crop_path).read_bytes(),
            identity_id=identities[crop.tracklet_id.rsplit("-", maxsplit=1)[-1]],
        ),
        kit_color_extractor=lambda crop: (
            ("red", "0,255,255")
            if crop.tracklet_id.endswith("000001")
            else ("blue", "120,255,255")
        ),
    ).process(RecordingContext(), project.project_id, source, checkpoint={})

    numbers = {
        "000001": "8",
        "000002": "11",
    }
    JerseyOCRStage(
        settings=settings,
        database=database,
        recognizer=FakeOCR(),
        crop_loader=lambda crop: CropInput(
            data=Path(crop.crop_path).read_bytes(),
            number=numbers[crop.tracklet_id.rsplit("-", maxsplit=1)[-1]],
        ),
    ).process(RecordingContext(), project.project_id, source, checkpoint={})

    AssembleCandidatesStage(
        settings=settings,
        database=database,
        evidence_builder=_fake_evidence,
    ).process(RecordingContext(), project.project_id, source)

    clusters = AnalysisRepository(database).list_clusters(source.source_id)
    assert len(clusters) == 2
    assert all(cluster.tracklet_count == 1 for cluster in clusters)
    assert {cluster.jersey_number for cluster in clusters} == {"8", "11"}
    response = TestClient(app).get(f"/projects/{project.project_id}/candidates")
    assert response.status_code == 200
    candidates = response.json()["candidates"]
    assert len(candidates) == 2
    assert all(len(candidate["evidence"]) == 10 for candidate in candidates)
    assert ProjectRepository(database).get(project.project_id).status == "awaiting_target_selection"


def _write_fake_crop(
    path: Path, box: DetectionBox, frame_height: int | None
) -> tuple[float, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xd8fake\xff\xd9")
    return 10.0, round(box.h * int(frame_height or 0))


def _fake_evidence(
    project_id: str,
    source_path: Path,
    cluster_id: str,
    crops,
) -> list[dict]:
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
