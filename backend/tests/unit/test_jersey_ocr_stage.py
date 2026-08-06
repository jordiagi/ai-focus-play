from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from src.app.config import Settings
from src.domain.models.detection import (
    IdentityCluster,
    JerseyVote,
    Tracklet,
    TrackletCrop,
    TrackletEmbedding,
)
from src.domain.models.project import AnalysisProject
from src.domain.models.selection import UserClick
from src.domain.models.video import SourceVideo
from src.ml.interfaces import CropInput, TextReading
from src.services.pipeline.jersey_ocr_stage import (
    JerseyOCRStage,
    _load_torso_crop,
    _winning_text,
)
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository
from tests.fakes.fake_models import FakeOCR


@dataclass
class RecordingContext:
    job_id: str = "ocr-job"
    cancelled: bool = False
    updates: list[tuple[float, str, dict | None]] = field(default_factory=list)

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None:
        self.updates.append((progress_pct, message, checkpoint))


class RecordingOCR:
    def __init__(self) -> None:
        self.seen: list[CropInput] = []
        self.batch_sizes: list[int] = []

    def recognize(self, crops: Sequence[CropInput]) -> list[TextReading]:
        self.seen.extend(crops)
        self.batch_sizes.append(len(crops))
        return FakeOCR().recognize(crops)


def _setup(tmp_path: Path) -> tuple[Settings, Database, SourceVideo]:
    settings = Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "app.db",
        ocr_keyframes_per_tracklet=8,
    )
    database = Database(settings.db_path)
    source = SourceVideo(
        source_id="s1",
        project_id="p1",
        file_path=str(tmp_path / "match.mp4"),
        duration_s=20,
        width=640,
        height=360,
    )
    ProjectRepository(database).create(
        AnalysisProject(project_id="p1", source_id=source.source_id)
    )
    SourceRepository(database).insert(source)
    return settings, database, source


def _seed_tracklet(
    repository: AnalysisRepository,
    tmp_path: Path,
    tracklet_id: str,
    cluster_id: str,
    readings: list[tuple[int, float, str]],
    *,
    start_ts: float = 0,
) -> dict[str, str]:
    repository.bulk_upsert_tracklets(
        [
            Tracklet(
                tracklet_id=tracklet_id,
                source_id="s1",
                start_ts=start_ts,
                end_ts=start_ts + max(1, len(readings)),
                frame_count=len(readings),
                cluster_id=cluster_id,
            )
        ]
    )
    numbers: dict[str, str] = {}
    crops = []
    for index, (height, sharpness, number) in enumerate(readings):
        crop_id = f"{tracklet_id}-c{index}"
        path = tmp_path / f"{crop_id}.jpg"
        path.write_bytes(crop_id.encode())
        numbers[crop_id] = number
        crops.append(
            TrackletCrop(
                crop_id=crop_id,
                tracklet_id=tracklet_id,
                ts=start_ts + float(index),
                crop_path=str(path),
                sharpness=sharpness,
                bbox_h_px=height,
            )
        )
    repository.bulk_insert_crops(crops)
    return numbers


def test_keyframes_require_60px_and_take_sharpest_eight(tmp_path: Path) -> None:
    settings, database, source = _setup(tmp_path)
    repository = AnalysisRepository(database)
    repository.bulk_upsert_clusters(
        [IdentityCluster("cluster-1", source.source_id, 1, 10)]
    )
    numbers = _seed_tracklet(
        repository,
        tmp_path,
        "t1",
        "cluster-1",
        [(59, 100, "9")] + [(100, float(value), "8") for value in range(10)],
    )
    recognizer = RecordingOCR()

    JerseyOCRStage(
        settings=settings,
        database=database,
        recognizer=recognizer,
        crop_loader=lambda crop: CropInput(
            data=crop.crop_path,
            number=numbers[crop.crop_id],
            metadata={"crop_id": crop.crop_id},
        ),
    ).process(RecordingContext(), "p1", source, checkpoint={})

    seen_ids = {item.metadata["crop_id"] for item in recognizer.seen}
    assert len(seen_ids) == 8
    assert "t1-c0" not in seen_ids
    assert "t1-c1" not in seen_ids
    assert "t1-c2" not in seen_ids
    assert len(repository.list_jersey_votes_for_tracklet("t1")) == 8


def test_votes_majority_per_tracklet_then_per_cluster(tmp_path: Path) -> None:
    settings, database, source = _setup(tmp_path)
    repository = AnalysisRepository(database)
    repository.bulk_upsert_clusters(
        [IdentityCluster("cluster-1", source.source_id, 3, 12)]
    )
    numbers = {}
    numbers.update(
        _seed_tracklet(
            repository,
            tmp_path,
            "t1",
            "cluster-1",
            [(100, 10, "8"), (100, 9, "8"), (100, 8, "11")],
        )
    )
    numbers.update(
        _seed_tracklet(
            repository,
            tmp_path,
            "t2",
            "cluster-1",
            [(100, 10, "8"), (100, 9, "8")],
        )
    )
    numbers.update(
        _seed_tracklet(
            repository,
            tmp_path,
            "t3",
            "cluster-1",
            [(100, 10, "11"), (100, 9, "11"), (100, 8, "11"), (100, 7, "11")],
        )
    )
    context = RecordingContext()

    JerseyOCRStage(
        settings=settings,
        database=database,
        recognizer=FakeOCR(),
        crop_loader=lambda crop: CropInput(
            data=crop.crop_path, number=numbers[crop.crop_id]
        ),
    ).process(context, "p1", source, checkpoint={})

    cluster = repository.list_clusters(source.source_id)[0]
    assert cluster.jersey_number == "8"
    assert cluster.jersey_conf == 2 / 3
    assert context.updates[-1][2] == {
        "done_tracklet_ids": ["t1", "t2", "t3"],
        "no_readable_numbers": False,
    }


def test_keyframes_from_multiple_tracklets_share_an_ocr_batch(tmp_path: Path) -> None:
    settings, database, source = _setup(tmp_path)
    repository = AnalysisRepository(database)
    repository.bulk_upsert_clusters(
        [IdentityCluster("cluster-1", source.source_id, 3, 12)]
    )
    numbers = {}
    for tracklet_id in ("t1", "t2", "t3"):
        numbers.update(
            _seed_tracklet(
                repository,
                tmp_path,
                tracklet_id,
                "cluster-1",
                [(100, 10, "8")],
            )
        )
    recognizer = RecordingOCR()

    JerseyOCRStage(
        settings=settings,
        database=database,
        recognizer=recognizer,
        crop_loader=lambda crop: CropInput(
            data=crop.crop_path,
            number=numbers[crop.crop_id],
        ),
    ).process(RecordingContext(), "p1", source, checkpoint={})

    assert recognizer.batch_sizes == [3]


def test_no_legible_readings_leave_cluster_null_and_set_flag(tmp_path: Path) -> None:
    settings, database, source = _setup(tmp_path)
    repository = AnalysisRepository(database)
    repository.bulk_upsert_clusters(
        [IdentityCluster("cluster-1", source.source_id, 1, 3)]
    )
    numbers = _seed_tracklet(
        repository,
        tmp_path,
        "t1",
        "cluster-1",
        [(100, 10, "")],
    )
    context = RecordingContext()

    JerseyOCRStage(
        settings=settings,
        database=database,
        recognizer=FakeOCR(),
        crop_loader=lambda crop: CropInput(
            data=crop.crop_path, number=numbers[crop.crop_id]
        ),
    ).process(context, "p1", source, checkpoint={})

    cluster = repository.list_clusters(source.source_id)[0]
    assert cluster.jersey_number is None
    assert cluster.jersey_conf is None
    assert context.updates[-1][2]["no_readable_numbers"] is True


def test_winning_text_requires_cross_frame_consensus() -> None:
    def vote(index: int, text: str, confidence: float) -> JerseyVote:
        return JerseyVote(
            vote_id=f"v{index}",
            tracklet_id="t1",
            ts=float(index),
            text=text,
            conf=confidence,
            model="parseq",
        )

    assert _winning_text(
        [
            vote(0, "38", 0.89),
            vote(1, "38", 0.93),
            vote(2, "38", 0.85),
            vote(3, "1", 0.70),
        ]
    ) == "38"
    assert _winning_text(
        [
            vote(0, "3", 0.71),
            vote(1, "1", 0.82),
            vote(2, "7", 0.68),
            vote(3, "1", 0.78),
        ]
    ) is None
    assert _winning_text([vote(0, "99", 0.99)]) is None


def test_torso_crop_focuses_on_the_jersey_number_region(tmp_path: Path) -> None:
    from PIL import Image

    path = tmp_path / "player.jpg"
    Image.new("RGB", (100, 200), "white").save(path)
    crop = TrackletCrop(
        crop_id="crop-1",
        tracklet_id="t1",
        ts=0,
        crop_path=str(path),
    )

    loaded = _load_torso_crop(crop)

    assert loaded.data.size == (70, 72)


def test_ocr_reclusters_clicked_hint_away_from_conflicting_number(
    tmp_path: Path,
) -> None:
    settings, database, source = _setup(tmp_path)
    repository = AnalysisRepository(database)
    repository.bulk_upsert_clusters(
        [IdentityCluster("old-cluster", source.source_id, 2, 8)]
    )
    numbers = {}
    numbers.update(
        _seed_tracklet(
            repository,
            tmp_path,
            "clicked-8",
            "old-cluster",
            [(100, 10, ""), (100, 9, "")],
        )
    )
    numbers.update(
        _seed_tracklet(
            repository,
            tmp_path,
            "later-38",
            "old-cluster",
            [
                (100, 10, "38"),
                (100, 9, "38"),
                (100, 8, "38"),
                (100, 7, "1"),
            ],
            start_ts=10,
        )
    )
    numbers.update(
        _seed_tracklet(
            repository,
            tmp_path,
            "earlier-clicked-8",
            "old-cluster",
            [(100, 10, ""), (100, 9, "")],
            start_ts=20,
        )
    )
    repository.bulk_upsert_embeddings(
        [
            TrackletEmbedding(
                "clicked-8",
                "dinov2-small",
                2,
                struct.pack("<2f", 1.0, 0.0),
                2,
            ),
            TrackletEmbedding(
                "later-38",
                "dinov2-small",
                2,
                struct.pack("<2f", 0.86, math.sqrt(1 - 0.86**2)),
                4,
            ),
            TrackletEmbedding(
                "earlier-clicked-8",
                "dinov2-small",
                2,
                struct.pack("<2f", 0.5, math.sqrt(1 - 0.5**2)),
                2,
            ),
        ]
    )
    ProjectRepository(database).set_jersey_hint("p1", "8")
    SelectionRepository(database).save_click(
        UserClick(
            click_id="earlier-click",
            project_id="p1",
            ts=20,
            x_norm=0.5,
            y_norm=0.5,
            label="positive",
            status="resolved",
            resolved_tracklet_id="earlier-clicked-8",
            created_at="2026-01-01T00:00:00+00:00",
        )
    )
    SelectionRepository(database).save_click(
        UserClick(
            click_id="click-1",
            project_id="p1",
            ts=0,
            x_norm=0.5,
            y_norm=0.5,
            label="positive",
            status="resolved",
            resolved_tracklet_id="clicked-8",
            created_at="2026-01-01T00:01:00+00:00",
        )
    )

    JerseyOCRStage(
        settings=settings,
        database=database,
        recognizer=FakeOCR(),
        crop_loader=lambda crop: CropInput(
            data=crop.crop_path,
            number=numbers[crop.crop_id],
        ),
    ).process(RecordingContext(), "p1", source, checkpoint={})

    clicked = repository.get_tracklet("clicked-8")
    earlier_clicked = repository.get_tracklet("earlier-clicked-8")
    conflicting = repository.get_tracklet("later-38")
    assert clicked.cluster_id != conflicting.cluster_id
    assert earlier_clicked.cluster_id != conflicting.cluster_id
    clusters = {
        cluster.cluster_id: cluster
        for cluster in repository.list_clusters(source.source_id)
    }
    assert clusters[clicked.cluster_id].jersey_number == "8"
    assert clusters[earlier_clicked.cluster_id].jersey_number == "8"
    assert {
        cluster.jersey_number
        for cluster in clusters.values()
    } == {"8", "38"}
