from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from src.app.dependencies import (
    analysis_repository,
    frame_service,
    job_repository,
    project_repository,
    source_repository,
)
from src.app.errors import AppError


router = APIRouter(tags=["frames"])


def _context(project_id: str):
    try:
        project = project_repository().get(project_id)
    except KeyError as exc:
        raise AppError("Project not found", status_code=404) from exc
    source = source_repository().get_for_project(project_id)
    if source is None:
        raise AppError("Add a video before choosing a frame.", status_code=409)
    return project, source


@router.get("/projects/{project_id}/frame")
def get_frame(project_id: str, t: float = Query(ge=0)) -> FileResponse:
    _, source = _context(project_id)
    path = frame_service().get_frame(project_id, source, t)
    return FileResponse(path, media_type="image/jpeg")


@router.get("/projects/{project_id}/frame-detections")
def get_frame_detections(project_id: str, t: float = Query(ge=0)) -> dict:
    project, source = _context(project_id)
    detections = analysis_repository().detections_near(source.source_id, t)
    if not detections:
        max_ts = analysis_repository().max_detection_ts(source.source_id)
        detect_jobs = [
            job
            for job in job_repository().list_for_project(project_id)
            if job.stage == "detect_track"
        ]
        if detect_jobs:
            latest = detect_jobs[-1]
            if latest.status == "succeeded":
                max_ts = max(float(max_ts or 0), float(source.duration_s or 0))
            elif latest.checkpoint.get("last_ts") is not None:
                max_ts = max(
                    float(max_ts or 0), float(latest.checkpoint["last_ts"])
                )
        return {
            "ts_actual": t,
            "analyzed": max_ts is not None and max_ts >= t - 0.5,
            "boxes": [],
        }
    boxes = []
    for detection in detections:
        cluster_id = None
        if detection.tracklet_id:
            try:
                cluster_id = analysis_repository().get_tracklet(
                    detection.tracklet_id
                ).cluster_id
            except KeyError:
                pass
        boxes.append(
            {
                "tracklet_id": detection.tracklet_id,
                "cluster_id": cluster_id,
                "x": detection.x,
                "y": detection.y,
                "w": detection.w,
                "h": detection.h,
                "is_target": bool(
                    project.target_cluster_id
                    and cluster_id == project.target_cluster_id
                ),
            }
        )
    return {"ts_actual": detections[0].ts, "analyzed": True, "boxes": boxes}
