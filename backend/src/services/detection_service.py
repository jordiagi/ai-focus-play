from __future__ import annotations

from uuid import uuid4

from src.domain.models.detection import PlayerDetection
from src.domain.models.project import AnalysisProject


class DetectionService:
    def generate_candidate_detections(self, project: AnalysisProject | str) -> list[PlayerDetection]:
        if isinstance(project, AnalysisProject):
            project_id = project.project_id
            first_start, first_end, second_start, second_end = self._candidate_windows(project)
        else:
            project_id = project
            first_start, first_end, second_start, second_end = 120.0, 140.0, 550.0, 568.0
        return [
            PlayerDetection(
                detection_id=str(uuid4()),
                project_id=project_id,
                start_time_seconds=first_start,
                end_time_seconds=first_end,
                frame_region={"x": 0.44, "y": 0.30, "w": 0.08, "h": 0.18},
                team_match_confidence=0.95,
                identity_confidence=0.92,
                review_state="auto_accepted",
                visual_cues_used=["team-color", "motion-continuity", "jersey-number"],
            ),
            PlayerDetection(
                detection_id=str(uuid4()),
                project_id=project_id,
                start_time_seconds=second_start,
                end_time_seconds=second_end,
                frame_region={"x": 0.56, "y": 0.26, "w": 0.07, "h": 0.17},
                team_match_confidence=0.91,
                identity_confidence=0.73,
                review_state="needs_review",
                visual_cues_used=["team-color", "body-shape"],
            ),
        ]

    def _candidate_windows(self, project: AnalysisProject) -> tuple[float, float, float, float]:
        start = max(0.0, project.match_window_start)
        end = project.match_window_end if project.match_window_end > start else start + 7200.0
        duration = max(1.0, end - start)
        segment_duration = min(20.0, max(0.5, duration * 0.25))
        first_start = start + duration * 0.10
        second_start = start + duration * 0.55
        return (
            first_start,
            min(end, first_start + segment_duration),
            second_start,
            min(end, second_start + segment_duration),
        )

    def verification_score(self, detections: list[PlayerDetection]) -> float:
        if not detections:
            return 0.0
        accepted = [d.identity_confidence for d in detections if d.review_state in {"auto_accepted", "approved"}]
        if not accepted:
            return 0.0
        return round(sum(accepted) / len(accepted), 2)
