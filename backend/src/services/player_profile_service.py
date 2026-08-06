from __future__ import annotations

from uuid import uuid4

from src.app.errors import AppError
from src.app.logging import log_event
from src.domain.models.player import TargetPlayerProfile
from src.domain.models.project import AnalysisProject, utcnow
from src.storage.project_repository import ProjectRepository


class PlayerProfileService:
    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository

    def confirm_player(
        self,
        project: AnalysisProject,
        team_side: str,
        team_color_notes: str,
        jersey_number: str,
        appearance_notes: str,
        reference_frames: list[float],
    ) -> TargetPlayerProfile:
        if not any([team_color_notes.strip(), jersey_number.strip(), appearance_notes.strip(), reference_frames]):
            raise AppError("At least one identifying cue is required", status_code=422)
        player = TargetPlayerProfile(
            target_player_profile_id=str(uuid4()),
            team_side=team_side,
            team_color_notes=team_color_notes,
            jersey_number=jersey_number,
            appearance_notes=appearance_notes,
            reference_frames=reference_frames,
            confirmation_status="confirmed",
        )
        self.repository.save_player(player)
        project.target_player_profile_id = player.target_player_profile_id
        project.status = "ready_for_player_confirmation"
        project.updated_at = utcnow()
        self.repository.save_project(project)
        log_event("player_confirmed", project_id=project.project_id, player_id=player.target_player_profile_id)
        return player

