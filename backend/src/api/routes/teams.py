import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.src.domain.models.match import Team
from backend.src.storage.repository import match_repo

logger = logging.getLogger("api_teams")
router = APIRouter(prefix="/api/teams", tags=["teams"])

class CreateTeamRequest(BaseModel):
    name: str
    club_name: Optional[str] = "Arlington Soccer"
    federation_url: Optional[str] = None

class UpdateTeamRequest(BaseModel):
    name: Optional[str] = None
    club_name: Optional[str] = None
    federation_url: Optional[str] = None

@router.get("", response_model=List[Team])
def list_teams():
    return match_repo.list_teams()

@router.post("", response_model=Team)
def create_team(req: CreateTeamRequest):
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Team name cannot be empty")
    return match_repo.create_team(
        name=req.name,
        club_name=req.club_name,
        federation_url=req.federation_url
    )

@router.get("/{team_id}", response_model=Team)
def get_team(team_id: str):
    team = match_repo.get_team(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team

@router.put("/{team_id}", response_model=Team)
def update_team(team_id: str, req: UpdateTeamRequest):
    team = match_repo.update_team(
        team_id=team_id,
        name=req.name,
        club_name=req.club_name,
        federation_url=req.federation_url
    )
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team

@router.delete("/{team_id}")
def delete_team(team_id: str):
    success = match_repo.delete_team(team_id)
    if not success:
        raise HTTPException(status_code=404, detail="Team not found")
    return {"status": "success", "message": f"Team {team_id} deleted"}
