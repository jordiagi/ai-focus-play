from __future__ import annotations

from src.app.errors import AppError
from src.app.logging import log_event
from src.services.timeline_service import TimelineService
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository


class IdentityService:
    def __init__(self, database: Database) -> None:
        self.analysis = AnalysisRepository(database)
        self.projects = ProjectRepository(database)
        self.selection = SelectionRepository(database)
        self.sources = SourceRepository(database)
        self.timeline = TimelineService(database)

    def confirm(self, project_id: str, cluster_id: str) -> dict:
        project = self.projects.get(project_id)
        source = self.sources.get_for_project(project_id)
        if source is None:
            raise AppError("Add a video before confirming your player.", status_code=409)
        clusters = self.analysis.list_clusters(source.source_id)
        selected = next(
            (cluster for cluster in clusters if cluster.cluster_id == cluster_id),
            None,
        )
        if selected is None:
            raise AppError("That player match is no longer available — click them again.", status_code=404)
        for cluster in clusters:
            cluster.status = "confirmed" if cluster.cluster_id == cluster_id else (
                "candidate" if cluster.status == "confirmed" else cluster.status
            )
        self.analysis.bulk_upsert_clusters(clusters)
        self.projects.set_target_cluster(project.project_id, cluster_id)
        coverage = self.timeline.rebuild(project_id, cluster_id)
        log_event(
            "identity_confirmed",
            project_id=project_id,
            cluster_id=cluster_id,
            segment_count=coverage["segment_count"],
        )
        return {"target_cluster_id": cluster_id, "coverage": coverage}

    def adjust(
        self,
        project_id: str,
        *,
        add_tracklet_ids: list[str],
        remove_tracklet_ids: list[str],
    ) -> dict:
        project = self.projects.get(project_id)
        if not project.target_cluster_id and add_tracklet_ids:
            raise AppError(
                "Confirm your player first — click them on a frame and check the evidence.",
                status_code=409,
            )
        source = self.sources.get_for_project(project_id)
        if source is None:
            raise AppError("The project video is not available.", status_code=409)
        available = {
            tracklet.tracklet_id: tracklet
            for tracklet in self.analysis.list_tracklets(source.source_id)
        }
        requested = set(add_tracklet_ids) | set(remove_tracklet_ids)
        if requested - set(available):
            raise AppError("One of those player appearances is no longer available.", status_code=404)
        prior_cluster_ids = {
            available[tracklet_id].cluster_id
            for tracklet_id in requested
            if available[tracklet_id].cluster_id
        }
        for tracklet_id in add_tracklet_ids:
            tracklet = available[tracklet_id]
            tracklet.cluster_id = project.target_cluster_id
            tracklet.cluster_assignment = "user_click"
        for tracklet_id in remove_tracklet_ids:
            tracklet = available[tracklet_id]
            tracklet.cluster_id = None
            tracklet.cluster_assignment = "user_removed"
        self.analysis.bulk_upsert_tracklets(
            available[tracklet_id] for tracklet_id in requested
        )
        for cluster_id in prior_cluster_ids:
            self._refresh_cluster(source.source_id, cluster_id)
        if project.target_cluster_id:
            self._refresh_cluster(source.source_id, project.target_cluster_id)
            coverage = self.timeline.rebuild(project_id, project.target_cluster_id)
        else:
            coverage = {"segment_count": 0, "total_s": 0.0, "gaps": []}
        log_event(
            "identity_adjusted",
            project_id=project_id,
            cluster_id=project.target_cluster_id,
            added=add_tracklet_ids,
            removed=remove_tracklet_ids,
            segment_count=coverage["segment_count"],
        )
        return {"coverage": coverage}

    def reset(self, project_id: str) -> None:
        project = self.projects.get(project_id)
        if project.target_cluster_id:
            source = self.sources.get_for_project(project_id)
            if source:
                clusters = self.analysis.list_clusters(source.source_id)
                for cluster in clusters:
                    if cluster.cluster_id == project.target_cluster_id:
                        cluster.status = "candidate"
                self.analysis.bulk_upsert_clusters(clusters)
        self.projects.set_target_cluster(project_id, None)
        self.selection.replace_segments(project_id, [])
        log_event("identity_reset", project_id=project_id)

    def _refresh_cluster(self, source_id: str, cluster_id: str) -> None:
        clusters = self.analysis.list_clusters(source_id)
        target = next(
            (cluster for cluster in clusters if cluster.cluster_id == cluster_id),
            None,
        )
        if target is None:
            return
        members = [
            tracklet
            for tracklet in self.analysis.list_tracklets(source_id)
            if tracklet.cluster_id == cluster_id
            and tracklet.cluster_assignment != "user_removed"
        ]
        target.tracklet_count = len(members)
        target.screen_time_s = sum(
            max(0.0, tracklet.end_ts - tracklet.start_ts)
            for tracklet in members
        )
        self.analysis.bulk_upsert_clusters([target])
