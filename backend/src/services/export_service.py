from __future__ import annotations

from typing import Callable
from uuid import uuid4

from src.app.errors import AppError
from src.app.logging import log_event
from src.domain.models.output import ReelOutput
from src.domain.models.project import AnalysisProject
from src.domain.models.selection import AppearanceSegment
from src.storage.output_repository import OutputRepository
from src.storage.selection_repository import SelectionRepository

# Rough per-profile duration budgets (seconds). full_appearances = everything.
_PROFILE_BUDGET_S: dict[str, float | None] = {
    "short_highlight": 45.0,
    "medium_best_plays": 180.0,
    "full_appearances": None,
}

_TARGET_NOT_CONFIRMED = (
    "Confirm your player first — click them on a frame and check the evidence."
)


class ExportService:
    """Create reel outputs and hand rendering off to the background export stage."""

    def __init__(
        self,
        outputs: OutputRepository,
        selection: SelectionRepository,
        projects,
        enqueue_export: Callable[[str, str], str],
    ) -> None:
        self.outputs = outputs
        self.selection = selection
        self.projects = projects
        self.enqueue_export = enqueue_export

    def create(
        self, project: AnalysisProject, profile: str, overlay_mode: str
    ) -> tuple[ReelOutput, str]:
        if not project.target_cluster_id:
            log_event("export_blocked_unconfirmed", project_id=project.project_id)
            raise AppError(_TARGET_NOT_CONFIRMED, status_code=409)
        if profile not in _PROFILE_BUDGET_S:
            raise AppError(
                "That reel length isn't available — pick short, medium, or full.",
                status_code=422,
            )

        included = [
            segment
            for segment in self.selection.list_segments(project.project_id)
            if segment.included
        ]
        selected = self._select_for_profile(included, profile)

        output = ReelOutput(
            output_id=uuid4().hex,
            project_id=project.project_id,
            profile=profile,
            overlay_mode=overlay_mode,
            status="queued",
            segment_ids=[segment.segment_id for segment in selected],
        )
        self.outputs.save(output)
        job_id = self.enqueue_export(project.project_id, output.output_id)
        log_event(
            "export_started",
            project_id=project.project_id,
            output_id=output.output_id,
            profile=profile,
            overlay_mode=overlay_mode,
            segment_count=len(selected),
            job_id=job_id,
        )
        return output, job_id

    @staticmethod
    def _select_for_profile(
        segments: list[AppearanceSegment], profile: str
    ) -> list[AppearanceSegment]:
        budget = _PROFILE_BUDGET_S[profile]
        if budget is None or not segments:
            return sorted(segments, key=lambda s: s.start_ts)
        # Greedily take the highest-scoring segments until the budget is reached,
        # then present them in chronological order for the reel.
        ranked = sorted(
            segments,
            key=lambda s: (-(s.score or (s.end_ts - s.start_ts)), s.start_ts),
        )
        chosen: list[AppearanceSegment] = []
        total = 0.0
        for segment in ranked:
            duration = max(0.0, segment.end_ts - segment.start_ts)
            if chosen and total + duration > budget:
                continue
            chosen.append(segment)
            total += duration
            if total >= budget:
                break
        return sorted(chosen, key=lambda s: s.start_ts)
