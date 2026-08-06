from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from src.app.config import Settings
from src.domain.models.detection import Tracklet, TrackletCrop
from src.domain.models.project import AnalysisProject
from src.domain.models.video import SourceVideo
from src.ml.interfaces import CropInput
from src.services.pipeline.embed_cluster_stage import (
    EmbedClusterStage,
    _constrained_agglomerative,
    _scalable_constrained_agglomerative,
)
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.project_repository import ProjectRepository
from src.storage.source_repository import SourceRepository
from tests.fakes.fake_models import FakeEmbedder


@dataclass
class RecordingContext:
    job_id: str = "embed-job"
    cancelled: bool = False
    updates: list[tuple[float, str, dict | None]] = field(default_factory=list)

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None:
        self.updates.append((progress_pct, message, checkpoint))


class RecordingEmbedder:
    def __init__(self) -> None:
        self.batch_sizes: list[int] = []

    def embed(self, crops):
        self.batch_sizes.append(len(crops))
        return FakeEmbedder().embed(crops)


def _setup(tmp_path: Path) -> tuple[Settings, Database, SourceVideo]:
    settings = Settings(
        data_dir=tmp_path / "data",
        db_path=tmp_path / "data" / "app.db",
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


def _seed(
    database: Database,
    tmp_path: Path,
    rows: list[tuple[str, float, float, str, str]],
) -> dict[str, str]:
    repository = AnalysisRepository(database)
    identities: dict[str, str] = {}
    tracklets = []
    crops = []
    for tracklet_id, start, end, identity, assignment in rows:
        identities[tracklet_id] = identity
        tracklets.append(
            Tracklet(
                tracklet_id=tracklet_id,
                source_id="s1",
                start_ts=start,
                end_ts=end,
                frame_count=max(1, round((end - start) * 6)),
                avg_conf=0.9,
                cluster_id="old-cluster" if assignment == "user_removed" else None,
                cluster_assignment=assignment,
            )
        )
        crop_path = tmp_path / f"{tracklet_id}.jpg"
        crop_path.write_bytes(tracklet_id.encode())
        crops.append(
            TrackletCrop(
                crop_id=f"crop-{tracklet_id}",
                tracklet_id=tracklet_id,
                ts=start,
                crop_path=str(crop_path),
                sharpness=10,
                bbox_h_px=100,
            )
        )
    repository.bulk_upsert_tracklets(tracklets)
    repository.bulk_insert_crops(crops)
    return identities


def _run(
    settings: Settings,
    database: Database,
    source: SourceVideo,
    identities: dict[str, str],
    *,
    embedder=None,
) -> RecordingContext:
    context = RecordingContext()
    stage = EmbedClusterStage(
        settings=settings,
        database=database,
        embedder=embedder or FakeEmbedder(),
        crop_loader=lambda crop: CropInput(
            data=Path(crop.crop_path).read_bytes(),
            identity_id=identities[crop.tracklet_id],
        ),
        kit_color_extractor=lambda _: (None, None),
    )
    stage.process(context, "p1", source, checkpoint={})
    return context


def test_two_identities_cluster_into_two_clusters(tmp_path: Path) -> None:
    settings, database, source = _setup(tmp_path)
    identities = _seed(
        database,
        tmp_path,
        [
            ("a-1", 0, 2, "player-a", "auto"),
            ("a-2", 3, 5, "player-a", "auto"),
            ("b-1", 0, 2, "player-b", "auto"),
            ("b-2", 3, 5, "player-b", "auto"),
        ],
    )

    context = _run(settings, database, source, identities)

    tracklets = AnalysisRepository(database).list_tracklets(source.source_id)
    by_identity = {
        identity: {tracklet.cluster_id for tracklet in tracklets if identities[tracklet.tracklet_id] == identity}
        for identity in {"player-a", "player-b"}
    }
    assert all(len(cluster_ids) == 1 for cluster_ids in by_identity.values())
    assert by_identity["player-a"] != by_identity["player-b"]
    assert len(AnalysisRepository(database).list_clusters(source.source_id)) == 2
    assert context.updates[-1][2] == {
        "embedded_tracklet_ids": ["a-1", "a-2", "b-1", "b-2"]
    }


def test_temporally_overlapping_tracklets_never_merge(tmp_path: Path) -> None:
    settings, database, source = _setup(tmp_path)
    identities = _seed(
        database,
        tmp_path,
        [
            ("same-1", 0, 4, "same-player", "auto"),
            ("same-2", 1, 5, "same-player", "auto"),
        ],
    )

    _run(settings, database, source, identities)

    tracklets = AnalysisRepository(database).list_tracklets(source.source_id)
    assert len({tracklet.cluster_id for tracklet in tracklets}) == 2


def test_crops_from_multiple_tracklets_share_an_embedding_batch(tmp_path: Path) -> None:
    settings, database, source = _setup(tmp_path)
    identities = _seed(
        database,
        tmp_path,
        [
            ("a", 0, 1, "player-a", "auto"),
            ("b", 2, 3, "player-b", "auto"),
            ("c", 4, 5, "player-c", "auto"),
        ],
    )
    embedder = RecordingEmbedder()

    _run(settings, database, source, identities, embedder=embedder)

    assert embedder.batch_sizes == [3]


def test_user_removed_tracklet_stays_excluded_after_recluster(tmp_path: Path) -> None:
    settings, database, source = _setup(tmp_path)
    identities = _seed(
        database,
        tmp_path,
        [
            ("kept", 0, 2, "same-player", "auto"),
            ("removed", 3, 5, "same-player", "user_removed"),
        ],
    )

    _run(settings, database, source, identities)
    _run(settings, database, source, identities)

    removed = AnalysisRepository(database).get_tracklet("removed")
    assert removed.cluster_assignment == "user_removed"
    assert removed.cluster_id is None


def test_large_input_uses_bounded_clusters_with_temporal_constraints() -> None:
    progress: list[tuple[int, int]] = []
    records: list[tuple[Tracklet, list[float]]] = []
    for moment in range(320):
        start = float(moment * 2)
        records.extend(
            [
                (
                    Tracklet(
                        tracklet_id=f"a-{moment}",
                        source_id="s1",
                        start_ts=start,
                        end_ts=start + 1,
                        frame_count=6,
                    ),
                    [1.0, 0.0],
                ),
                (
                    Tracklet(
                        tracklet_id=f"b-{moment}",
                        source_id="s1",
                        start_ts=start,
                        end_ts=start + 1,
                        frame_count=6,
                    ),
                    [0.0, 1.0],
                ),
            ]
        )

    groups = _scalable_constrained_agglomerative(
        records,
        0.35,
        on_progress=lambda completed, total: progress.append((completed, total)),
    )

    assert len(groups) == 2
    assert {
        frozenset(
            records[index][0].tracklet_id.split("-", maxsplit=1)[0]
            for index in group
        )
        for group in groups
    } == {
        frozenset({"a"}),
        frozenset({"b"}),
    }
    assert progress[-1] == (640, 640)


def test_large_input_fallback_does_not_force_conflicting_kit_colors_together() -> None:
    records: list[tuple[Tracklet, list[float]]] = []
    for index in range(64):
        vector = [0.0] * 64
        vector[index] = 1.0
        records.append(
            (
                Tracklet(
                    tracklet_id=f"prototype-{index}",
                    source_id="s1",
                    start_ts=float(index * 2),
                    end_ts=float(index * 2 + 1),
                    frame_count=6,
                    kit_color_name="red" if index == 63 else "blue",
                ),
                vector,
            )
        )
    incoming = [0.0] * 64
    incoming[0] = 0.7
    incoming[1] = (1 - 0.7**2) ** 0.5
    records.append(
        (
            Tracklet(
                tracklet_id="incoming-red",
                source_id="s1",
                start_ts=130.0,
                end_ts=131.0,
                frame_count=6,
                kit_color_name="red",
            ),
            incoming,
        )
    )

    groups = _scalable_constrained_agglomerative(records, 0.35)
    incoming_group = next(group for group in groups if 64 in group)

    assert {
        records[index][0].kit_color_name for index in incoming_group
    } == {"red"}


def test_reliable_jersey_mismatch_separates_visually_similar_tracklets() -> None:
    records = [
        (
            Tracklet("player-8", "s1", 0, 1, 6),
            [1.0, 0.0],
        ),
        (
            Tracklet("player-38", "s1", 2, 3, 6),
            [0.86, (1 - 0.86**2) ** 0.5],
        ),
    ]

    assert len(_constrained_agglomerative(records, 0.35)) == 1
    assert len(
        _constrained_agglomerative(
            records,
            0.35,
            jersey_numbers={"player-8": "8", "player-38": "38"},
        )
    ) == 2


def test_large_input_fallback_respects_reliable_jersey_numbers() -> None:
    records: list[tuple[Tracklet, list[float]]] = []
    jersey_numbers: dict[str, str] = {}
    for index in range(64):
        tracklet_id = f"prototype-{index}"
        vector = [0.0] * 64
        vector[index] = 1.0
        records.append(
            (
                Tracklet(
                    tracklet_id=tracklet_id,
                    source_id="s1",
                    start_ts=float(index * 2),
                    end_ts=float(index * 2 + 1),
                    frame_count=6,
                ),
                vector,
            )
        )
        jersey_numbers[tracklet_id] = "38" if index == 63 else "8"
    incoming = [0.0] * 64
    incoming[0] = 0.7
    incoming[1] = (1 - 0.7**2) ** 0.5
    records.append(
        (
            Tracklet("incoming-38", "s1", 130, 131, 6),
            incoming,
        )
    )
    jersey_numbers["incoming-38"] = "38"

    groups = _scalable_constrained_agglomerative(
        records,
        0.35,
        jersey_numbers=jersey_numbers,
    )
    incoming_group = next(group for group in groups if 64 in group)

    assert {
        jersey_numbers[records[index][0].tracklet_id]
        for index in incoming_group
    } == {"38"}
