from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha1
from pathlib import Path
from typing import Any, Callable, Protocol

from src.app.config import Settings, get_settings
from src.domain.models.detection import JerseyVote, TrackletCrop
from src.domain.models.video import SourceVideo
from src.ml.interfaces import CropInput, TextRecognizer
from src.services.pipeline.embed_cluster_stage import recluster_existing_embeddings
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.job_repository import JobRepository
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository


class ProgressContext(Protocol):
    job_id: str
    cancelled: bool

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None: ...


CropLoader = Callable[[TrackletCrop], CropInput]


class JerseyOCRStage:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        recognizer: TextRecognizer,
        crop_loader: CropLoader | None = None,
        crop_batch_size: int = 32,
    ) -> None:
        self.settings = settings
        self.repository = AnalysisRepository(database)
        self.projects = ProjectRepository(database)
        self.selections = SelectionRepository(database)
        self.recognizer = recognizer
        self.crop_loader = crop_loader or _load_torso_crop
        self.crop_batch_size = max(1, crop_batch_size)

    def process(
        self,
        context: ProgressContext,
        project_id: str,
        source: SourceVideo,
        *,
        checkpoint: dict[str, Any],
    ) -> None:
        tracklets = sorted(
            (
                tracklet
                for tracklet in self.repository.list_tracklets(source.source_id)
                if not tracklet.synthetic
                and tracklet.cluster_assignment != "user_removed"
            ),
            key=lambda tracklet: tracklet.tracklet_id,
        )
        done = set(checkpoint.get("done_tracklet_ids", []))
        checkpoint_interval = max(20, len(tracklets) // 20)
        pending: list[tuple[str, list[TrackletCrop], list[CropInput]]] = []
        pending_crop_count = 0

        def flush_pending() -> None:
            nonlocal pending_crop_count
            if not pending:
                return
            inputs = [item for _, _, items in pending for item in items]
            readings = self.recognizer.recognize(inputs)
            if len(readings) != len(inputs):
                raise RuntimeError("Text recognizer returned an invalid crop batch")
            votes_by_tracklet: dict[str, list[JerseyVote]] = {}
            offset = 0
            for tracklet_id, keyframes, items in pending:
                tracklet_readings = readings[offset : offset + len(items)]
                offset += len(items)
                votes = []
                for crop, reading in zip(keyframes, tracklet_readings):
                    text = "".join(
                        character for character in reading.text if character.isdigit()
                    )
                    if not 1 <= len(text) <= 2:
                        continue
                    vote_id = "vote-" + sha1(
                        f"{tracklet_id}:{crop.crop_id}:parseq".encode()
                    ).hexdigest()[:20]
                    votes.append(
                        JerseyVote(
                            vote_id=vote_id,
                            tracklet_id=tracklet_id,
                            ts=crop.ts,
                            crop_path=crop.crop_path,
                            text=text,
                            conf=reading.confidence,
                            model="parseq",
                        )
                    )
                votes_by_tracklet[tracklet_id] = votes
                done.add(tracklet_id)
            self.repository.replace_jersey_votes_batch(votes_by_tracklet)
            pending.clear()
            pending_crop_count = 0

        for index, tracklet in enumerate(tracklets, start=1):
            if context.cancelled:
                return
            if tracklet.tracklet_id not in done:
                keyframes = _select_keyframes(
                    self.repository.list_crops(tracklet.tracklet_id),
                    self.settings.ocr_keyframes_per_tracklet,
                )
                if keyframes:
                    inputs = [self.crop_loader(crop) for crop in keyframes]
                    pending.append((tracklet.tracklet_id, keyframes, inputs))
                    pending_crop_count += len(inputs)
                    if pending_crop_count >= self.crop_batch_size:
                        flush_pending()
                else:
                    done.add(tracklet.tracklet_id)
            if index == len(tracklets) or index % checkpoint_interval == 0:
                flush_pending()
                context.update(
                    85.0 * index / max(1, len(tracklets)),
                    f"Reading jersey numbers — {index} of {len(tracklets)} appearances",
                    {"done_tracklet_ids": sorted(done)},
                )

        no_readable_numbers = self._aggregate(
            project_id,
            source.source_id,
            on_progress=lambda completed, total: context.update(
                85 + (14 * completed / max(1, total)),
                f"Using jersey readings to separate players — {completed} of {total}",
                {"done_tracklet_ids": sorted(done)},
            ),
        )
        context.update(
            100,
            "Reading jersey numbers — finished",
            {
                "done_tracklet_ids": sorted(done),
                "no_readable_numbers": no_readable_numbers,
            },
        )

    def _aggregate(
        self,
        project_id: str,
        source_id: str,
        *,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> bool:
        tracklets = self.repository.list_tracklets(source_id)
        tracklet_winners: dict[str, str] = {}
        votes_by_tracklet: dict[str, list[JerseyVote]] = defaultdict(list)
        for vote in self.repository.list_jersey_votes(source_id):
            votes_by_tracklet[vote.tracklet_id].append(vote)
        for tracklet_id, votes in votes_by_tracklet.items():
            winner = _winning_text(votes)
            if winner:
                tracklet_winners[tracklet_id] = winner

        readable_ocr_numbers = bool(tracklet_winners)
        project = self.projects.get(project_id)
        if project.jersey_hint:
            for click in self.selections.list_clicks(project_id):
                if (
                    click.label == "positive"
                    and click.status == "resolved"
                    and click.resolved_tracklet_id
                ):
                    tracklet_winners[click.resolved_tracklet_id] = (
                        project.jersey_hint
                    )

        recluster_existing_embeddings(
            self.repository,
            source_id,
            jersey_numbers=tracklet_winners,
            on_progress=on_progress,
        )
        tracklets = self.repository.list_tracklets(source_id)

        by_cluster: dict[str, list[str]] = defaultdict(list)
        for tracklet in tracklets:
            if tracklet.cluster_id and tracklet.tracklet_id in tracklet_winners:
                by_cluster[tracklet.cluster_id].append(
                    tracklet_winners[tracklet.tracklet_id]
                )
        clusters = self.repository.list_clusters(source_id)
        for cluster in clusters:
            winners = by_cluster.get(cluster.cluster_id, [])
            if winners:
                counts = Counter(winners)
                jersey_number, count = min(
                    counts.items(), key=lambda item: (-item[1], item[0])
                )
                cluster.jersey_number = jersey_number
                cluster.jersey_conf = count / len(winners)
            else:
                cluster.jersey_number = None
                cluster.jersey_conf = None
        self.repository.bulk_upsert_clusters(clusters)
        return not readable_ocr_numbers


def run_jersey_ocr_stage(context: ProgressContext, _: dict[str, Any]) -> None:
    from src.ml.impl.parseq_ocr import PARSeqRecognizer

    settings = get_settings()
    database = Database(settings.db_path)
    job = JobRepository(database).get(context.job_id)
    project = ProjectRepository(database).get(job.project_id)
    if not project.source_id:
        raise RuntimeError("Project has no source video")
    source = SourceRepository(database).get(project.source_id)
    JerseyOCRStage(
        settings=settings,
        database=database,
        recognizer=PARSeqRecognizer(),
    ).process(
        context,
        project.project_id,
        source,
        checkpoint=job.checkpoint,
    )


def _select_keyframes(
    crops: list[TrackletCrop], limit: int
) -> list[TrackletCrop]:
    eligible = [crop for crop in crops if int(crop.bbox_h_px or 0) >= 60]
    return sorted(
        eligible,
        key=lambda crop: (
            -float(crop.sharpness or 0),
            -int(crop.bbox_h_px or 0),
            crop.ts,
            crop.crop_id,
        ),
    )[: max(1, limit)]


def _winning_text(votes: list[JerseyVote]) -> str | None:
    eligible = [
        vote for vote in votes if vote.text.isdigit() and 1 <= len(vote.text) <= 2
    ]
    counts = Counter(vote.text for vote in eligible)
    if not counts:
        return None
    confidence = defaultdict(float)
    for vote in eligible:
        confidence[vote.text] += vote.conf
    winner = min(
        counts,
        key=lambda text: (-counts[text], -confidence[text], text),
    )
    if counts[winner] < 2 or counts[winner] / len(eligible) < 0.6:
        return None
    return winner


def _load_torso_crop(crop: TrackletCrop) -> CropInput:
    from PIL import Image

    with Image.open(Path(crop.crop_path)) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        torso = rgb.crop(
            (
                round(width * 0.15),
                round(height * 0.20),
                round(width * 0.85),
                max(round(height * 0.56), 1),
            )
        )
    return CropInput(
        data=torso,
        metadata={"tracklet_id": crop.tracklet_id, "ts": crop.ts},
    )
