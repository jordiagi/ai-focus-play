from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.app.dependencies import (
    analysis_repository,
    click_service,
    project_repository,
    selection_repository,
)
from src.app.errors import AppError


router = APIRouter(tags=["clicks"])


class ClickRequest(BaseModel):
    t: float = Field(ge=0)
    x_norm: float = Field(ge=0, le=1)
    y_norm: float = Field(ge=0, le=1)
    label: Literal["positive", "negative"]


def _project_or_404(project_id: str) -> None:
    try:
        project_repository().get(project_id)
    except KeyError as exc:
        raise AppError("Project not found", status_code=404) from exc


@router.post("/projects/{project_id}/clicks")
def post_click(project_id: str, request: ClickRequest) -> dict:
    _project_or_404(project_id)
    return click_service().submit_click(
        project_id,
        t=request.t,
        x_norm=request.x_norm,
        y_norm=request.y_norm,
        label=request.label,
    )


@router.get("/projects/{project_id}/clicks")
def get_clicks(project_id: str) -> dict[str, list[dict]]:
    _project_or_404(project_id)
    payload = []
    for click in selection_repository().list_clicks(project_id):
        cluster_id = None
        if click.resolved_tracklet_id:
            try:
                cluster_id = analysis_repository().get_tracklet(
                    click.resolved_tracklet_id
                ).cluster_id
            except KeyError:
                pass
        payload.append(
            {
                "click_id": click.click_id,
                "t": click.ts,
                "x_norm": click.x_norm,
                "y_norm": click.y_norm,
                "label": click.label,
                "status": click.status,
                "resolved_tracklet_id": click.resolved_tracklet_id,
                "cluster_id": cluster_id,
            }
        )
    return {"clicks": payload}
