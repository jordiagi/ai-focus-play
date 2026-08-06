from __future__ import annotations

import math
import struct
from collections import Counter
from hashlib import sha1
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from src.app.config import Settings, get_settings
from src.domain.models.detection import (
    IdentityCluster,
    Tracklet,
    TrackletCrop,
    TrackletEmbedding,
)
from src.domain.models.video import SourceVideo
from src.ml.interfaces import CropInput, Embedder
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.job_repository import JobRepository
from src.storage.project_repository import ProjectRepository
from src.storage.source_repository import SourceRepository


class ProgressContext(Protocol):
    job_id: str
    cancelled: bool

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None: ...


CropLoader = Callable[[TrackletCrop], CropInput]
KitColorExtractor = Callable[[TrackletCrop], tuple[str | None, str | None]]
JERSEY_MISMATCH_PENALTY = 0.25


class EmbedClusterStage:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        embedder: Embedder,
        crop_loader: CropLoader | None = None,
        kit_color_extractor: KitColorExtractor | None = None,
        distance_threshold: float = 0.35,
        crop_batch_size: int = 64,
    ) -> None:
        self.settings = settings
        self.database = database
        self.repository = AnalysisRepository(database)
        self.embedder = embedder
        self.crop_loader = crop_loader or _load_crop
        self.kit_color_extractor = kit_color_extractor or _extract_kit_color
        self.distance_threshold = distance_threshold
        self.crop_batch_size = max(1, crop_batch_size)

    def process(
        self,
        context: ProgressContext,
        project_id: str,
        source: SourceVideo,
        *,
        checkpoint: dict[str, Any],
    ) -> None:
        repaired_tracklets = self.repository.repair_discontinuous_tracklets(
            source.source_id,
            project_id,
        )
        if repaired_tracklets:
            context.update(
                0,
                f"Restored {repaired_tracklets} continuous player appearances",
                {"embedded_tracklet_ids": []},
            )
        tracklets = sorted(
            (
                tracklet
                for tracklet in self.repository.list_tracklets(source.source_id)
                if not tracklet.synthetic
                and tracklet.cluster_assignment != "user_removed"
            ),
            key=lambda tracklet: tracklet.tracklet_id,
        )
        existing = {
            item.tracklet_id: item
            for item in self.repository.list_embeddings(source.source_id)
        }
        embedded = set(checkpoint.get("embedded_tracklet_ids", [])) | set(existing)
        checkpoint_interval = max(20, len(tracklets) // 20)
        pending: list[tuple[Tracklet, list[TrackletCrop], list[CropInput]]] = []
        pending_crop_count = 0

        def flush_pending() -> None:
            nonlocal pending_crop_count
            if not pending:
                return
            inputs = [item for _, _, items in pending for item in items]
            vectors = self.embedder.embed(inputs)
            if len(vectors) != len(inputs) or not vectors:
                raise RuntimeError("Embedder returned an invalid crop batch")
            embeddings: list[TrackletEmbedding] = []
            updated_tracklets: list[Tracklet] = []
            offset = 0
            for tracklet, crops, items in pending:
                tracklet_vectors = vectors[offset : offset + len(items)]
                offset += len(items)
                vector = _normalize(_mean_vector(tracklet_vectors))
                embedding = TrackletEmbedding(
                    tracklet_id=tracklet.tracklet_id,
                    model="dinov2-small",
                    dim=len(vector),
                    vector=struct.pack(f"<{len(vector)}f", *vector),
                    crop_count=len(crops),
                )
                embeddings.append(embedding)
                existing[tracklet.tracklet_id] = embedding
                representative = max(
                    crops,
                    key=lambda crop: (
                        float(crop.sharpness or 0),
                        int(crop.bbox_h_px or 0),
                    ),
                )
                color_name, color_hsv = self.kit_color_extractor(representative)
                tracklet.kit_color_name = color_name
                tracklet.kit_color_hsv = color_hsv
                updated_tracklets.append(tracklet)
                embedded.add(tracklet.tracklet_id)
            self.repository.bulk_upsert_embeddings(embeddings)
            self.repository.bulk_upsert_tracklets(updated_tracklets)
            pending.clear()
            pending_crop_count = 0

        for index, tracklet in enumerate(tracklets, start=1):
            if context.cancelled:
                return
            if tracklet.tracklet_id not in existing:
                crops = self.repository.list_crops(tracklet.tracklet_id)
                if crops:
                    inputs = [self.crop_loader(crop) for crop in crops]
                    pending.append((tracklet, crops, inputs))
                    pending_crop_count += len(inputs)
                    if pending_crop_count >= self.crop_batch_size:
                        flush_pending()
            else:
                embedded.add(tracklet.tracklet_id)
            if index == len(tracklets) or index % checkpoint_interval == 0:
                flush_pending()
                context.update(
                    85.0 * index / max(1, len(tracklets)),
                    f"Learning what each player looks like — {index} of {len(tracklets)} appearances",
                    {"embedded_tracklet_ids": sorted(embedded)},
                )

        refreshed = {
            tracklet.tracklet_id: tracklet
            for tracklet in self.repository.list_tracklets(source.source_id)
            if not tracklet.synthetic
            and tracklet.cluster_assignment != "user_removed"
        }
        records = sorted(
            (
                (refreshed[tracklet_id], _unpack_embedding(embedding))
                for tracklet_id, embedding in existing.items()
                if tracklet_id in refreshed
            ),
            key=lambda record: (
                record[0].start_ts,
                record[0].end_ts,
                record[0].tracklet_id,
            ),
        )
        saved_checkpoint = {"embedded_tracklet_ids": sorted(embedded)}
        context.update(
            85,
            f"Embedding complete — grouping {len(records)} appearances into players",
            saved_checkpoint,
        )
        groups = _constrained_agglomerative(
            records,
            self.distance_threshold,
            on_progress=lambda completed, total: context.update(
                85 + (13 * completed / max(1, total)),
                f"Grouping appearances into players — {completed} of {total}",
                saved_checkpoint,
            ),
        )
        context.update(
            99,
            f"Preparing {len(groups)} player candidates",
            saved_checkpoint,
        )
        clusters = _replace_clusters(
            self.repository,
            source.source_id,
            records,
            groups,
        )
        context.update(
            100,
            f"Learning what each player looks like — found {len(clusters)} candidates",
            {"embedded_tracklet_ids": sorted(embedded)},
        )


def run_embed_cluster_stage(context: ProgressContext, _: dict[str, Any]) -> None:
    from src.ml.impl.dinov2_embedder import DINOv2Embedder

    settings = get_settings()
    database = Database(settings.db_path)
    job = JobRepository(database).get(context.job_id)
    project = ProjectRepository(database).get(job.project_id)
    if not project.source_id:
        raise RuntimeError("Project has no source video")
    source = SourceRepository(database).get(project.source_id)
    EmbedClusterStage(
        settings=settings,
        database=database,
        embedder=DINOv2Embedder(),
    ).process(
        context,
        project.project_id,
        source,
        checkpoint=job.checkpoint,
    )


def _constrained_agglomerative(
    records: list[tuple[Tracklet, list[float]]],
    threshold: float,
    *,
    jersey_numbers: dict[str, str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[list[int]]:
    jersey_numbers = jersey_numbers or {}
    if len(records) > 64:
        return _scalable_constrained_agglomerative(
            records,
            threshold,
            jersey_numbers=jersey_numbers,
            on_progress=on_progress,
        )

    groups = [[index] for index in range(len(records))]
    while True:
        best: tuple[float, int, int] | None = None
        for left in range(len(groups)):
            for right in range(left + 1, len(groups)):
                if _groups_overlap(groups[left], groups[right], records):
                    continue
                distance = _group_distance(
                    groups[left],
                    groups[right],
                    records,
                    jersey_numbers,
                )
                if best is None or distance < best[0]:
                    best = (distance, left, right)
        if best is None or best[0] > threshold:
            break
        _, left, right = best
        groups[left] = groups[left] + groups[right]
        del groups[right]
    if on_progress:
        on_progress(len(records), len(records))
    return groups


def _scalable_constrained_agglomerative(
    records: list[tuple[Tracklet, list[float]]],
    threshold: float,
    *,
    jersey_numbers: dict[str, str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[list[int]]:
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - the production ML extra includes NumPy
        raise RuntimeError("Large-match clustering requires the backend ML dependencies") from exc

    total = len(records)
    if not total:
        return []
    jersey_numbers = jersey_numbers or {}
    vectors = np.asarray([vector for _, vector in records], dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != total:
        raise RuntimeError("Embedding dimensions do not match")

    # Poor detections can produce tens of thousands of short tracklets. Keep a
    # bounded prototype set so clustering stays linear in match length while a
    # hard temporal check still prevents simultaneous players from sharing one.
    soft_group_limit = min(256, max(64, math.ceil(math.sqrt(total))))
    centroids = np.zeros((total, vectors.shape[1]), dtype=np.float32)
    counts = np.zeros(total, dtype=np.int32)
    max_ends = np.full(total, -np.inf, dtype=np.float64)
    colors: list[set[str]] = []
    jerseys: list[set[str]] = []
    groups: list[list[int]] = []
    progress_interval = max(1, total // 100)

    for index, (tracklet, _) in enumerate(records):
        vector = vectors[index]
        group_count = len(groups)
        selected: int | None = None
        selected_distance = math.inf

        if group_count:
            overlap_s = (
                np.minimum(max_ends[:group_count], tracklet.end_ts)
                - tracklet.start_ts
            )
            eligible = np.flatnonzero(overlap_s <= 0.5)
            if eligible.size:
                distances = 1.0 - centroids[:group_count].dot(vector)
                if tracklet.kit_color_name:
                    mismatched = np.fromiter(
                        (
                            bool(group_colors)
                            and tracklet.kit_color_name not in group_colors
                            for group_colors in colors
                        ),
                        dtype=np.bool_,
                        count=group_count,
                    )
                    distances = distances + (0.08 * mismatched)
                jersey_number = jersey_numbers.get(tracklet.tracklet_id)
                if jersey_number:
                    mismatched = np.fromiter(
                        (
                            bool(group_jerseys)
                            and jersey_number not in group_jerseys
                            for group_jerseys in jerseys
                        ),
                        dtype=np.bool_,
                        count=group_count,
                    )
                    distances = distances + (
                        JERSEY_MISMATCH_PENALTY * mismatched
                    )
                best_offset = int(np.argmin(distances[eligible]))
                selected = int(eligible[best_offset])
                selected_distance = float(distances[selected])
                # The prototype cap is a performance fallback, not evidence that
                # an over-threshold, conflicting kit or number is the same player.
                if (
                    selected_distance > threshold
                    and group_count >= soft_group_limit
                    and (tracklet.kit_color_name or jersey_number)
                ):
                    compatible = np.asarray(
                        [
                            group_index
                            for group_index in eligible
                            if (
                                not tracklet.kit_color_name
                                or not colors[int(group_index)]
                                or tracklet.kit_color_name
                                in colors[int(group_index)]
                            )
                            and (
                                not jersey_number
                                or not jerseys[int(group_index)]
                                or jersey_number
                                in jerseys[int(group_index)]
                            )
                        ],
                        dtype=np.int64,
                    )
                    if compatible.size:
                        best_offset = int(np.argmin(distances[compatible]))
                        selected = int(compatible[best_offset])
                        selected_distance = float(distances[selected])
                    else:
                        selected = None
                        selected_distance = math.inf

        if (
            selected is None
            or (
                selected_distance > threshold
                and group_count < soft_group_limit
            )
        ):
            selected = group_count
            groups.append([])
            colors.append(set())
            jerseys.append(set())
            centroids[selected] = vector
        else:
            count = int(counts[selected])
            centroids[selected] = (
                (centroids[selected] * count) + vector
            ) / (count + 1)

        groups[selected].append(index)
        counts[selected] += 1
        max_ends[selected] = max(max_ends[selected], tracklet.end_ts)
        if tracklet.kit_color_name:
            colors[selected].add(tracklet.kit_color_name)
        jersey_number = jersey_numbers.get(tracklet.tracklet_id)
        if jersey_number:
            jerseys[selected].add(jersey_number)

        completed = index + 1
        if on_progress and (
            completed == total or completed % progress_interval == 0
        ):
            on_progress(completed, total)

    return groups


def _groups_overlap(
    left: list[int],
    right: list[int],
    records: list[tuple[Tracklet, list[float]]],
) -> bool:
    return any(
        min(records[a][0].end_ts, records[b][0].end_ts)
        - max(records[a][0].start_ts, records[b][0].start_ts)
        > 0.5
        for a in left
        for b in right
    )


def _group_distance(
    left: list[int],
    right: list[int],
    records: list[tuple[Tracklet, list[float]]],
    jersey_numbers: dict[str, str] | None = None,
) -> float:
    visual = sum(
        _cosine_distance(records[a][1], records[b][1])
        for a in left
        for b in right
    ) / (len(left) * len(right))
    left_colors = {records[index][0].kit_color_name for index in left} - {None}
    right_colors = {records[index][0].kit_color_name for index in right} - {None}
    color_penalty = (
        0.08
        if left_colors
        and right_colors
        and left_colors.isdisjoint(right_colors)
        else 0.0
    )
    jersey_numbers = jersey_numbers or {}
    left_jerseys = {
        jersey_numbers[records[index][0].tracklet_id]
        for index in left
        if records[index][0].tracklet_id in jersey_numbers
    }
    right_jerseys = {
        jersey_numbers[records[index][0].tracklet_id]
        for index in right
        if records[index][0].tracklet_id in jersey_numbers
    }
    jersey_penalty = (
        JERSEY_MISMATCH_PENALTY
        if left_jerseys and right_jerseys and left_jerseys.isdisjoint(right_jerseys)
        else 0.0
    )
    return visual + color_penalty + jersey_penalty


def recluster_existing_embeddings(
    repository: AnalysisRepository,
    source_id: str,
    *,
    distance_threshold: float = 0.35,
    jersey_numbers: dict[str, str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[IdentityCluster]:
    tracklets = {
        tracklet.tracklet_id: tracklet
        for tracklet in repository.list_tracklets(source_id)
        if not tracklet.synthetic
        and tracklet.cluster_assignment != "user_removed"
    }
    records = sorted(
        (
            (tracklets[item.tracklet_id], _unpack_embedding(item))
            for item in repository.list_embeddings(source_id)
            if item.tracklet_id in tracklets
        ),
        key=lambda record: (
            record[0].start_ts,
            record[0].end_ts,
            record[0].tracklet_id,
        ),
    )
    if not records:
        return repository.list_clusters(source_id)
    groups = _constrained_agglomerative(
        records,
        distance_threshold,
        jersey_numbers=jersey_numbers,
        on_progress=on_progress,
    )
    return _replace_clusters(
        repository,
        source_id,
        records,
        groups,
        jersey_numbers=jersey_numbers,
    )


def _replace_clusters(
    repository: AnalysisRepository,
    source_id: str,
    records: list[tuple[Tracklet, list[float]]],
    groups: list[list[int]],
    *,
    jersey_numbers: dict[str, str] | None = None,
) -> list[IdentityCluster]:
    jersey_numbers = jersey_numbers or {}
    clusters: list[IdentityCluster] = []
    assignments: dict[str, str] = {}
    for group in groups:
        members = [records[index][0] for index in group]
        member_ids = sorted(member.tracklet_id for member in members)
        digest = sha1(
            (source_id + ":" + ",".join(member_ids)).encode()
        ).hexdigest()[:16]
        cluster_id = f"cluster-{digest}"
        crops = [
            crop
            for member in members
            for crop in repository.list_crops(member.tracklet_id)
        ]
        representative = max(
            crops,
            key=lambda crop: (
                float(crop.sharpness or 0),
                int(crop.bbox_h_px or 0),
            ),
            default=None,
        )
        colors = [
            member.kit_color_name for member in members if member.kit_color_name
        ]
        numbers = [
            jersey_numbers[member.tracklet_id]
            for member in members
            if member.tracklet_id in jersey_numbers
        ]
        number_counts = Counter(numbers)
        jersey_number, jersey_count = (
            min(number_counts.items(), key=lambda item: (-item[1], item[0]))
            if number_counts
            else (None, 0)
        )
        clusters.append(
            IdentityCluster(
                cluster_id=cluster_id,
                source_id=source_id,
                tracklet_count=len(members),
                screen_time_s=sum(
                    max(0.0, member.end_ts - member.start_ts)
                    for member in members
                ),
                jersey_number=jersey_number,
                jersey_conf=jersey_count / len(numbers) if numbers else None,
                kit_color_name=(
                    Counter(colors).most_common(1)[0][0] if colors else None
                ),
                rep_crop_path=representative.crop_path if representative else None,
            )
        )
        assignments.update({member.tracklet_id: cluster_id for member in members})
    repository.replace_candidate_clusters(source_id, clusters, assignments)
    return clusters


def _cosine_distance(first: Sequence[float], second: Sequence[float]) -> float:
    return 1.0 - sum(a * b for a, b in zip(first, second))


def _mean_vector(vectors: Sequence[Sequence[float]]) -> list[float]:
    dimension = len(vectors[0])
    if any(len(vector) != dimension for vector in vectors):
        raise RuntimeError("Embedding dimensions do not match")
    return [
        sum(vector[index] for vector in vectors) / len(vectors)
        for index in range(dimension)
    ]


def _normalize(vector: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [float(value) / norm for value in vector]


def _unpack_embedding(embedding: TrackletEmbedding) -> list[float]:
    return list(struct.unpack(f"<{embedding.dim}f", embedding.vector))


def _load_crop(crop: TrackletCrop) -> CropInput:
    return CropInput(
        data=Path(crop.crop_path),
        metadata={"tracklet_id": crop.tracklet_id, "ts": crop.ts},
    )


def _extract_kit_color(crop: TrackletCrop) -> tuple[str | None, str | None]:
    try:
        import cv2
        import numpy as np
        from sklearn.cluster import KMeans

        image = cv2.imread(crop.crop_path)
        if image is None or image.size == 0:
            return None, None
        height, width = image.shape[:2]
        torso = image[max(0, round(height * 0.12)) : max(1, round(height * 0.62)), :]
        hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV).reshape(-1, 3)
        if len(hsv) > 4_000:
            indices = np.linspace(0, len(hsv) - 1, 4_000, dtype=int)
            hsv = hsv[indices]
        count = min(3, len(hsv))
        model = KMeans(n_clusters=count, random_state=0, n_init=5).fit(hsv)
        sizes = np.bincount(model.labels_, minlength=count)
        centers = model.cluster_centers_
        usable = [
            index
            for index, center in enumerate(centers)
            if center[1] >= 45 and center[2] >= 40
        ]
        selected = max(usable or range(count), key=lambda index: sizes[index])
        hue, saturation, value = (round(float(item)) for item in centers[selected])
        return _color_name(hue, saturation, value), f"{hue},{saturation},{value}"
    except (ImportError, ValueError):
        return None, None


def _color_name(hue: int, saturation: int, value: int) -> str:
    if value < 55:
        return "black"
    if saturation < 40:
        return "white" if value > 180 else "gray"
    if hue < 10 or hue >= 170:
        return "red"
    if hue < 25:
        return "orange"
    if hue < 38:
        return "yellow"
    if hue < 85:
        return "green"
    if hue < 135:
        return "blue"
    if hue < 165:
        return "purple"
    return "pink"
