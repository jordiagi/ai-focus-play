from __future__ import annotations

from typing import Callable
from uuid import uuid4

from src.app.logging import log_event
from src.domain.models.detection import Detection
from src.domain.models.selection import UserClick
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.job_repository import JobRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository


PINNED_MESSAGE = (
    "Got them — we'll match this player across the match as we finish watching."
)
NO_PLAYER_MESSAGE = (
    "We don't see a player there — try clicking directly on their body."
)

MissResolver = Callable[[UserClick], dict]
JobStarter = Callable[[], object]


class ClickService:
    def __init__(
        self,
        database: Database,
        *,
        miss_resolver: MissResolver | None = None,
        job_starter: JobStarter | None = None,
    ) -> None:
        self.analysis = AnalysisRepository(database)
        self.jobs = JobRepository(database)
        self.selection = SelectionRepository(database)
        self.sources = SourceRepository(database)
        self.miss_resolver = miss_resolver or _no_player_resolution
        self.job_starter = job_starter

    def submit_click(
        self,
        project_id: str,
        *,
        t: float,
        x_norm: float,
        y_norm: float,
        label: str,
    ) -> dict:
        source = self.sources.get_for_project(project_id)
        if source is None:
            raise KeyError(project_id)
        click = UserClick(
            click_id=str(uuid4()),
            project_id=project_id,
            ts=t,
            x_norm=x_norm,
            y_norm=y_norm,
            label=label,
            status="pinned",
        )
        log_event(
            "click_received",
            click_id=click.click_id,
            project_id=project_id,
            ts=t,
            label=label,
        )
        hit = self._hit_test(source.source_id, t, x_norm, y_norm)
        if hit is not None and hit.tracklet_id:
            tracklet = self.analysis.get_tracklet(hit.tracklet_id)
            click.status = "resolved"
            click.resolved_tracklet_id = hit.tracklet_id
            self.selection.save_click(click)
            log_event(
                "click_resolved",
                click_id=click.click_id,
                tracklet_id=hit.tracklet_id,
                cluster_id=tracklet.cluster_id,
            )
            return {
                "click_id": click.click_id,
                "resolution": "tracklet",
                "tracklet_id": hit.tracklet_id,
                "cluster_id": tracklet.cluster_id,
                "box": {"x": hit.x, "y": hit.y, "w": hit.w, "h": hit.h},
            }

        analyzed_through = self._analyzed_through(project_id, source.duration_s)
        if analyzed_through is None or t > analyzed_through + 0.5:
            self.selection.save_click(click)
            log_event("click_pinned", click_id=click.click_id, ts=t)
            return {
                "click_id": click.click_id,
                "resolution": "pinned",
                "message": PINNED_MESSAGE,
            }

        resolution = self.miss_resolver(click)
        kind = resolution.get("resolution")
        if kind == "sam2_queued":
            click.status = "refining"
            click.sam2_job_id = resolution.get("job_id")
        else:
            click.status = "no_player"
            resolution = {
                "resolution": "no_player_here",
                "message": NO_PLAYER_MESSAGE,
            }
        self.selection.save_click(click)
        if kind == "sam2_queued" and self.job_starter is not None:
            self.job_starter()
        log_event(
            "click_resolved",
            click_id=click.click_id,
            resolution=resolution["resolution"],
        )
        return {"click_id": click.click_id, **resolution}

    def _hit_test(
        self, source_id: str, t: float, x_norm: float, y_norm: float
    ) -> Detection | None:
        hits = [
            detection
            for detection in self.analysis.detections_in_range(
                source_id, t - 0.5, t + 0.5
            )
            if detection.tracklet_id
            and detection.x <= x_norm <= detection.x + detection.w
            and detection.y <= y_norm <= detection.y + detection.h
        ]
        if not hits:
            return None
        return min(
            hits,
            key=lambda detection: (
                (detection.x + detection.w / 2 - x_norm) ** 2
                + (detection.y + detection.h / 2 - y_norm) ** 2,
                abs(detection.ts - t),
                detection.w * detection.h,
            ),
        )

    def _analyzed_through(
        self, project_id: str, duration_s: float | None
    ) -> float | None:
        source = self.sources.get_for_project(project_id)
        maximum = self.analysis.max_detection_ts(source.source_id) if source else None
        detect_jobs = [
            job
            for job in self.jobs.list_for_project(project_id)
            if job.stage == "detect_track"
        ]
        if detect_jobs:
            latest = detect_jobs[-1]
            if latest.status == "succeeded":
                maximum = max(float(maximum or 0), float(duration_s or 0))
            elif latest.checkpoint.get("last_ts") is not None:
                maximum = max(
                    float(maximum or 0), float(latest.checkpoint["last_ts"])
                )
        return float(maximum) if maximum is not None else None


def _no_player_resolution(_: UserClick) -> dict:
    return {"resolution": "no_player_here", "message": NO_PLAYER_MESSAGE}
