from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

from src.app.config import Settings, get_settings
from src.domain.models.detection import TrackletCrop
from src.domain.models.video import SourceVideo
from src.services.artifact_service import ArtifactService
from src.services.evidence_artifact_service import EvidenceArtifactService
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


EvidenceBuilder = Callable[
    [str, Path, str, Sequence[TrackletCrop]], list[dict]
]


class AssembleCandidatesStage:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        evidence_builder: EvidenceBuilder | None = None,
    ) -> None:
        self.settings = settings
        self.repository = AnalysisRepository(database)
        self.projects = ProjectRepository(database)
        self.artifacts = ArtifactService(settings)
        self.evidence_builder = evidence_builder or EvidenceArtifactService(
            self.artifacts, settings
        ).build_candidate_evidence

    def process(
        self,
        context: ProgressContext,
        project_id: str,
        source: SourceVideo,
    ) -> None:
        project = self.projects.get(project_id)
        clusters = self.repository.list_clusters(source.source_id)
        source_path = self.artifacts.resolve_source_path(
            project_id,
            source.proxy_path
            if source.proxy_status == "ready" and source.proxy_path
            else source.file_path,
        )
        written: set[Path] = set()
        assembled_cluster_ids: set[str] = set()
        source_tracklets = self.repository.list_tracklets(source.source_id)
        for index, cluster in enumerate(clusters, start=1):
            if context.cancelled:
                return
            tracklets = [
                tracklet
                for tracklet in source_tracklets
                if tracklet.cluster_id == cluster.cluster_id
                and tracklet.cluster_assignment != "user_removed"
                and not tracklet.synthetic
            ]
            tracklet_ids = {tracklet.tracklet_id for tracklet in tracklets}
            crops = _spread_crops(
                [
                    crop
                    for crop in self.repository.list_crops_for_cluster(
                        cluster.cluster_id
                    )
                    if crop.tracklet_id in tracklet_ids
                ],
                max(8, min(12, self.settings.evidence_sample_count)),
            )
            evidence = self.evidence_builder(
                project_id, source_path, cluster.cluster_id, crops
            )
            rep_crop_uri = _copy_representative_crop(
                self.artifacts,
                project_id,
                cluster.cluster_id,
                cluster.rep_crop_path,
            )
            if not rep_crop_uri and evidence:
                rep_crop_uri = evidence[0]["thumbnail_uri"]
            votes = self.repository.list_jersey_votes_for_cluster(cluster.cluster_id)
            agrees = (
                None
                if not project.jersey_hint or not votes
                else sum(vote.text == project.jersey_hint for vote in votes)
                > len(votes) / 2
            )
            rank_factor = 1.25 if agrees is True else 0.75 if agrees is False else 1.0
            payload = {
                "cluster_id": cluster.cluster_id,
                "jersey_number": cluster.jersey_number,
                "jersey_agreement": {
                    "readings": len(votes),
                    "agrees_with_hint": agrees,
                },
                "kit_color_name": cluster.kit_color_name,
                "screen_time_s": cluster.screen_time_s,
                "tracklet_count": cluster.tracklet_count,
                "rep_crop_uri": rep_crop_uri or "",
                "evidence": evidence,
                "timeline_spans": [
                    {
                        "start_ts": tracklet.start_ts,
                        "end_ts": tracklet.end_ts,
                    }
                    for tracklet in sorted(tracklets, key=lambda item: item.start_ts)
                ],
                "rank_score": cluster.screen_time_s * rank_factor,
            }
            written.add(
                write_candidate_manifest(
                    self.settings, project_id, cluster.cluster_id, payload
                )
            )
            assembled_cluster_ids.add(cluster.cluster_id)
            context.update(
                100.0 * index / max(1, len(clusters)),
                f"Preparing player choices — {index} of {len(clusters)}",
                {"assembled_cluster_ids": sorted(assembled_cluster_ids)},
            )

        for path in self.artifacts.evidence_dir(project_id).glob("candidate-*.json"):
            if path not in written:
                path.unlink(missing_ok=True)
        self.projects.update_status(project_id, "awaiting_target_selection")
        if not clusters:
            context.update(
                100,
                "Preparing player choices — no candidates found",
                {"assembled_cluster_ids": []},
            )


def write_candidate_manifest(
    settings: Settings,
    project_id: str,
    cluster_id: str,
    payload: dict[str, Any],
) -> Path:
    artifacts = ArtifactService(settings)
    path = artifacts.create_evidence_path(
        project_id, f"candidate-{cluster_id}.json"
    )
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    return path


def load_candidate_manifests(
    settings: Settings, project_id: str
) -> list[dict[str, Any]]:
    directory = ArtifactService(settings).evidence_dir(project_id)
    candidates: list[dict[str, Any]] = []
    for path in sorted(directory.glob("candidate-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("cluster_id"), str):
            candidates.append(payload)
    return candidates


def run_assemble_candidates_stage(
    context: ProgressContext, _: dict[str, Any]
) -> None:
    settings = get_settings()
    database = Database(settings.db_path)
    job = JobRepository(database).get(context.job_id)
    project = ProjectRepository(database).get(job.project_id)
    if not project.source_id:
        raise RuntimeError("Project has no source video")
    source = SourceRepository(database).get(project.source_id)
    AssembleCandidatesStage(settings=settings, database=database).process(
        context, project.project_id, source
    )


def _spread_crops(
    crops: Sequence[TrackletCrop], count: int
) -> list[TrackletCrop]:
    ordered = sorted(crops, key=lambda crop: (crop.ts, crop.crop_id))
    if len(ordered) <= count:
        return ordered
    if count <= 1:
        return [ordered[len(ordered) // 2]]
    indices = {
        round(index * (len(ordered) - 1) / (count - 1))
        for index in range(count)
    }
    return [ordered[index] for index in sorted(indices)]


def _copy_representative_crop(
    artifacts: ArtifactService,
    project_id: str,
    cluster_id: str,
    stored_path: str | None,
) -> str | None:
    if not stored_path:
        return None
    source = Path(stored_path)
    if not source.is_file():
        return None
    name = f"candidate-{cluster_id}-rep.jpg"
    destination = artifacts.create_evidence_path(project_id, name)
    if not destination.is_file():
        shutil.copyfile(source, destination)
    return artifacts.evidence_media_uri(project_id, name)
