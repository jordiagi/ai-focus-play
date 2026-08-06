from __future__ import annotations

import math
import shutil
import subprocess
from collections import Counter, defaultdict
from hashlib import sha1
from pathlib import Path
from typing import Any, Callable, Protocol

from src.app.config import Settings, get_settings
from src.domain.models.detection import (
    Detection,
    IdentityCluster,
    Tracklet,
    TrackletCrop,
)
from src.domain.models.video import SourceVideo
from src.ml.interfaces import FrameInput, MaskObservation, MaskPropagator
from src.services.artifact_service import ArtifactService
from src.services.timeline_service import TimelineService
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


FrameLoader = Callable[
    [Path, float, float, float, Path],
    list[FrameInput],
]


class Sam2RefineStage:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        propagator: MaskPropagator,
        frame_loader: FrameLoader | None = None,
    ) -> None:
        self.settings = settings
        self.analysis = AnalysisRepository(database)
        self.projects = ProjectRepository(database)
        self.selection = SelectionRepository(database)
        self.timeline = TimelineService(database)
        self.artifacts = ArtifactService(settings)
        self.propagator = propagator
        self.frame_loader = frame_loader or load_proxy_window

    def process(
        self,
        context: ProgressContext,
        project_id: str,
        source: SourceVideo,
        *,
        params: dict[str, Any],
    ) -> None:
        click_id = str(params.get("click_id") or "")
        if not click_id:
            raise RuntimeError("Refinement job has no click")
        click = self.selection.get_click(click_id)
        if click.project_id != project_id:
            raise RuntimeError("Refinement click belongs to another project")
        if source.proxy_status != "ready" or not source.proxy_path:
            raise RuntimeError("The proxy video is not ready for refinement")

        start_ts = max(0.0, click.ts - self.settings.sam2_window_s)
        end_ts = min(
            float(source.duration_s or click.ts + self.settings.sam2_window_s),
            click.ts + self.settings.sam2_window_s,
        )
        workspace = self.artifacts.masks_dir(project_id, click.click_id)
        try:
            context.update(2, "Taking a closer look — preparing nearby frames")
            frames = self.frame_loader(
                Path(source.proxy_path),
                start_ts,
                end_ts,
                self.settings.analysis_fps,
                workspace,
            )
            if not frames:
                self.selection.update_click_status(click_id, "no_player")
                context.update(100, "We couldn't find a player at that moment")
                return
            if context.cancelled:
                return
            seed_index = min(
                range(len(frames)),
                key=lambda index: abs(frames[index].ts - click.ts),
            )
            context.update(10, "Taking a closer look — following that player")
            observations = self.propagator.propagate(
                frames,
                seed_index,
                (click.x_norm, click.y_norm),
            )
            if context.cancelled:
                return
            self._persist_results(
                context,
                project_id,
                source,
                click_id,
                frames,
                observations,
            )
        finally:
            shutil.rmtree(workspace, ignore_errors=True)

    def _persist_results(
        self,
        context: ProgressContext,
        project_id: str,
        source: SourceVideo,
        click_id: str,
        frames: list[FrameInput],
        observations: list[MaskObservation],
    ) -> None:
        votes: Counter[str] = Counter()
        seen: Counter[str] = Counter()
        iou_totals: defaultdict[str, float] = defaultdict(float)
        unmatched: list[tuple[FrameInput, MaskObservation]] = []
        valid_masks = 0
        detection_window = (0.5 / max(self.settings.analysis_fps, 0.1)) + 1e-4

        for observation in observations:
            if observation.box is None or observation.score <= 0:
                continue
            if not 0 <= observation.frame_index < len(frames):
                continue
            valid_masks += 1
            frame = frames[observation.frame_index]
            detections = self.analysis.detections_near(
                source.source_id,
                frame.ts,
                detection_window,
            )
            for detection in detections:
                if detection.tracklet_id:
                    seen[detection.tracklet_id] += 1
            matches = sorted(
                (
                    (_iou(observation.box, _detection_box(detection)), detection)
                    for detection in detections
                ),
                key=lambda item: item[0],
                reverse=True,
            )
            best_iou, best_detection = matches[0] if matches else (0.0, None)
            if (
                best_detection is not None
                and best_detection.tracklet_id
                and best_iou >= 0.3
            ):
                votes[best_detection.tracklet_id] += 1
                iou_totals[best_detection.tracklet_id] += best_iou
            elif best_iou < 0.1:
                unmatched.append((frame, observation))

        accepted = {
            tracklet_id
            for tracklet_id, count in votes.items()
            if count >= max(1, math.ceil(seen[tracklet_id] * 0.5))
            and iou_totals[tracklet_id] / count >= 0.3
        }
        project = self.projects.get(project_id)
        target_cluster_id = self._target_cluster_id(
            project_id,
            source.source_id,
            project.target_cluster_id,
            accepted,
            votes,
            click_id,
        )

        updated = []
        for tracklet_id in accepted:
            tracklet = self.analysis.get_tracklet(tracklet_id)
            tracklet.cluster_id = target_cluster_id
            tracklet.cluster_assignment = "user_click"
            updated.append(tracklet)
        self.analysis.bulk_upsert_tracklets(updated)
        synthetic = self._mint_synthetic_tracklets(
            project_id,
            source,
            click_id,
            target_cluster_id,
            unmatched,
        )
        resolved_ids = [*accepted, *(item.tracklet_id for item in synthetic)]
        if not valid_masks or not resolved_ids:
            self.selection.update_click_status(click_id, "no_player")
            context.update(100, "We couldn't find a player at that moment")
            return

        self._refresh_clusters(source.source_id, target_cluster_id)
        resolved_tracklet_id = max(
            resolved_ids,
            key=lambda tracklet_id: (
                votes.get(tracklet_id, 0),
                self.analysis.get_tracklet(tracklet_id).frame_count,
                tracklet_id,
            ),
        )
        self.selection.update_click_status(
            click_id,
            "resolved",
            resolved_tracklet_id=resolved_tracklet_id,
        )
        if project.target_cluster_id:
            self.timeline.rebuild(project_id, project.target_cluster_id)
        context.update(
            100,
            "Taking a closer look — player added",
            {
                "matched_tracklet_ids": sorted(accepted),
                "synthetic_tracklet_ids": sorted(
                    item.tracklet_id for item in synthetic
                ),
            },
        )

    def _target_cluster_id(
        self,
        project_id: str,
        source_id: str,
        confirmed_cluster_id: str | None,
        accepted: set[str],
        votes: Counter[str],
        click_id: str,
    ) -> str:
        if confirmed_cluster_id:
            return confirmed_cluster_id
        prior_clicks = [
            click
            for click in self.selection.list_clicks(project_id)
            if click.click_id != click_id
            and click.label == "positive"
            and click.status == "resolved"
            and click.resolved_tracklet_id
        ]
        for click in reversed(prior_clicks):
            tracklet = self.analysis.get_tracklet(str(click.resolved_tracklet_id))
            if tracklet.cluster_id:
                return tracklet.cluster_id
        for tracklet_id, _ in votes.most_common():
            if tracklet_id not in accepted:
                continue
            cluster_id = self.analysis.get_tracklet(tracklet_id).cluster_id
            if cluster_id:
                return cluster_id
        cluster_id = "cluster-sam2-" + sha1(
            f"{source_id}:{click_id}".encode()
        ).hexdigest()[:16]
        self.analysis.bulk_upsert_clusters(
            [IdentityCluster(cluster_id, source_id, 0, 0)]
        )
        return cluster_id

    def _mint_synthetic_tracklets(
        self,
        project_id: str,
        source: SourceVideo,
        click_id: str,
        cluster_id: str,
        unmatched: list[tuple[FrameInput, MaskObservation]],
    ) -> list[Tracklet]:
        if not unmatched:
            return []
        max_gap = 1.5 / max(self.settings.analysis_fps, 0.1)
        groups: list[list[tuple[FrameInput, MaskObservation]]] = []
        for item in sorted(unmatched, key=lambda pair: pair[0].ts):
            if not groups or item[0].ts - groups[-1][-1][0].ts > max_gap:
                groups.append([])
            groups[-1].append(item)

        tracklets = []
        detections = []
        crops = []
        for group in groups:
            first_ts = group[0][0].ts
            tracklet_id = "synthetic-" + sha1(
                f"{source.source_id}:{click_id}:{first_ts:.3f}".encode()
            ).hexdigest()[:20]
            tracklet = Tracklet(
                tracklet_id=tracklet_id,
                source_id=source.source_id,
                start_ts=first_ts,
                end_ts=group[-1][0].ts,
                frame_count=len(group),
                avg_conf=sum(item[1].score for item in group) / len(group),
                cluster_id=cluster_id,
                cluster_assignment="user_click",
                synthetic=True,
            )
            tracklets.append(tracklet)
            for frame, observation in group:
                assert observation.box is not None
                x, y, width, height = observation.box
                detections.append(
                    Detection(
                        source_id=source.source_id,
                        tracklet_id=tracklet_id,
                        ts=frame.ts,
                        x=x,
                        y=y,
                        w=width,
                        h=height,
                        conf=observation.score,
                    )
                )
            crop = _write_synthetic_crop(
                self.artifacts,
                project_id,
                tracklet_id,
                group[0][0],
                group[0][1],
            )
            if crop:
                crops.append(crop)
        self.analysis.bulk_upsert_tracklets(tracklets)
        self.analysis.bulk_insert_detections(detections)
        self.analysis.bulk_insert_crops(crops)
        return tracklets

    def _refresh_clusters(self, source_id: str, target_cluster_id: str) -> None:
        tracklets = self.analysis.list_tracklets(source_id)
        clusters = self.analysis.list_clusters(source_id)
        target = next(
            (item for item in clusters if item.cluster_id == target_cluster_id),
            None,
        )
        if target is None:
            target = IdentityCluster(target_cluster_id, source_id, 0, 0)
            clusters.append(target)
        for cluster in clusters:
            members = [
                item
                for item in tracklets
                if item.cluster_id == cluster.cluster_id
                and item.cluster_assignment != "user_removed"
            ]
            cluster.tracklet_count = len(members)
            cluster.screen_time_s = sum(
                max(0.0, item.end_ts - item.start_ts) for item in members
            )
        self.analysis.bulk_upsert_clusters(clusters)


def run_sam2_refine_stage(context: ProgressContext, params: dict[str, Any]) -> None:
    from src.ml.impl.sam2_propagator import SAM2Propagator

    settings = get_settings()
    database = Database(settings.db_path)
    job = JobRepository(database).get(context.job_id)
    project = ProjectRepository(database).get(job.project_id)
    if not project.source_id:
        raise RuntimeError("Project has no source video")
    source = SourceRepository(database).get(project.source_id)
    Sam2RefineStage(
        settings=settings,
        database=database,
        propagator=SAM2Propagator(),
    ).process(
        context,
        project.project_id,
        source,
        params=params,
    )


def load_proxy_window(
    proxy_path: Path,
    start_ts: float,
    end_ts: float,
    fps: float,
    workspace: Path,
) -> list[FrameInput]:
    workspace.mkdir(parents=True, exist_ok=True)
    pattern = workspace / "%05d.jpg"
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{start_ts:.3f}",
            "-i",
            str(proxy_path),
            "-t",
            f"{max(0.0, end_ts - start_ts):.3f}",
            "-vf",
            f"fps={fps}",
            "-q:v",
            "3",
            "-start_number",
            "0",
            str(pattern),
        ],
        capture_output=True,
        text=True,
    )
    paths = sorted(workspace.glob("*.jpg"))
    if result.returncode != 0 or not paths:
        raise RuntimeError(
            "FFmpeg could not prepare the refinement window: "
            + result.stderr.strip()
        )
    from PIL import Image

    frames = []
    for index, path in enumerate(paths):
        with Image.open(path) as image:
            width, height = image.size
        frames.append(
            FrameInput(
                data=path,
                ts=start_ts + index / fps,
                width=width,
                height=height,
            )
        )
    return frames


def _write_synthetic_crop(
    artifacts: ArtifactService,
    project_id: str,
    tracklet_id: str,
    frame: FrameInput,
    observation: MaskObservation,
) -> TrackletCrop | None:
    if observation.box is None:
        return None
    from PIL import Image

    image = Image.open(frame.data) if isinstance(frame.data, (str, Path)) else frame.data
    if not isinstance(image, Image.Image):
        image = Image.fromarray(image)
    rgb = image.convert("RGB")
    x, y, width, height = observation.box
    crop = rgb.crop(
        (
            round(x * rgb.width),
            round(y * rgb.height),
            round((x + width) * rgb.width),
            round((y + height) * rgb.height),
        )
    )
    crop_id = f"{tracklet_id}-{round(frame.ts * 1000):010d}"
    path = artifacts.crops_dir(project_id, tracklet_id) / f"{crop_id}.jpg"
    crop.save(path, quality=92)
    if image is not frame.data:
        image.close()
    return TrackletCrop(
        crop_id=crop_id,
        tracklet_id=tracklet_id,
        ts=frame.ts,
        crop_path=str(path),
        bbox_h_px=round(height * rgb.height),
        purpose="sam2",
    )


def _detection_box(detection: Detection) -> tuple[float, float, float, float]:
    return detection.x, detection.y, detection.w, detection.h


def _iou(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    left = max(first[0], second[0])
    top = max(first[1], second[1])
    right = min(first[0] + first[2], second[0] + second[2])
    bottom = min(first[1] + first[3], second[1] + second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = (first[2] * first[3]) + (second[2] * second[3]) - intersection
    return intersection / union if union > 0 else 0.0
