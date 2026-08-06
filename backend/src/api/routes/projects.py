from __future__ import annotations

from collections import Counter
from uuid import uuid4

from fastapi import APIRouter, Query, Response
from fastapi.responses import FileResponse

from src.api.schemas.projects import (
    CreateProjectRequest,
    JerseyHintRequest,
    ProjectResponse,
    ProjectSummaryResponse,
    TargetAdjustRequest,
    TargetRequest,
    TimelineSegmentPatchRequest,
)
from src.app.dependencies import (
    analysis_repository,
    artifact_service,
    cleanup_service,
    evidence_artifact_service,
    job_repository,
    identity_service,
    project_repository,
    settings,
    source_repository,
    timeline_service,
)
from src.app.errors import AppError
from src.domain.models.project import AnalysisProject
from src.services.pipeline.assemble_candidates_stage import load_candidate_manifests


router = APIRouter(prefix="/projects", tags=["projects"])


def _project_or_404(project_id: str) -> AnalysisProject:
    try:
        return project_repository().get(project_id)
    except KeyError as exc:
        raise AppError("Project not found", status_code=404) from exc


def _summary(project: AnalysisProject) -> ProjectSummaryResponse:
    return ProjectSummaryResponse(
        project_id=project.project_id,
        name=project.name,
        status=project.status,
        source_id=project.source_id,
        target_cluster_id=project.target_cluster_id,
        updated_at=project.updated_at,
    )


def build_response(project: AnalysisProject) -> ProjectResponse:
    source = source_repository().get_for_project(project.project_id)
    jobs = job_repository().list_for_project(project.project_id)
    if not jobs:
        overall_status = "not_started"
    elif any(job.status == "failed" for job in jobs):
        overall_status = "failed"
    elif any(job.status in {"queued", "running"} for job in jobs):
        overall_status = "running"
    else:
        overall_status = "complete"
    latest_ocr = next(
        (job for job in reversed(jobs) if job.stage == "jersey_ocr"), None
    )
    return ProjectResponse(
        **_summary(project).model_dump(),
        created_at=project.created_at,
        jersey_hint=project.jersey_hint,
        source=source.to_dict() if source else None,
        analysis={
            "overall_status": overall_status,
            "no_readable_jersey_numbers": bool(
                latest_ocr
                and latest_ocr.status == "succeeded"
                and latest_ocr.checkpoint.get("no_readable_numbers")
            ),
            "stages": [
                {
                    "stage": job.stage,
                    "status": job.status,
                    "progress_pct": job.progress_pct,
                    "progress_message": job.progress_message,
                }
                for job in jobs
            ],
        },
    )


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(request: CreateProjectRequest) -> ProjectResponse:
    project = AnalysisProject(project_id=str(uuid4()), name=request.name.strip())
    project_repository().create(project)
    return build_response(project)


@router.get("", response_model=list[ProjectSummaryResponse])
def list_projects() -> list[ProjectSummaryResponse]:
    return [_summary(project) for project in project_repository().list()]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str) -> ProjectResponse:
    return build_response(_project_or_404(project_id))


@router.get("/{project_id}/candidates")
def get_candidates(
    project_id: str,
    cluster_id: str | None = Query(default=None),
    anchor_tracklet_id: str | None = Query(default=None),
    anchor_ts: float | None = Query(default=None),
) -> dict[str, list[dict]]:
    project = _project_or_404(project_id)
    candidates = load_candidate_manifests(settings(), project_id)
    source = source_repository().get_for_project(project_id)
    clusters = {
        cluster.cluster_id: cluster
        for cluster in (
            analysis_repository().list_clusters(source.source_id) if source else []
        )
    }
    tracklets = analysis_repository().list_tracklets(source.source_id) if source else []
    for candidate in candidates:
        current_cluster = clusters.get(candidate["cluster_id"])
        if current_cluster:
            active_tracklet_ids = {
                tracklet.tracklet_id
                for tracklet in tracklets
                if tracklet.cluster_id == current_cluster.cluster_id
                and tracklet.cluster_assignment != "user_removed"
            }
            candidate["evidence"] = [
                item
                for item in candidate.get("evidence", [])
                if item.get("tracklet_id") in active_tracklet_ids
            ]
            candidate["timeline_spans"] = [
                {"start_ts": item.start_ts, "end_ts": item.end_ts}
                for item in tracklets
                if item.tracklet_id in active_tracklet_ids
            ]
            candidate["tracklet_count"] = current_cluster.tracklet_count
            candidate["screen_time_s"] = current_cluster.screen_time_s
            color_counts = Counter(
                tracklet.kit_color_name
                for tracklet in tracklets
                if tracklet.tracklet_id in active_tracklet_ids
                and tracklet.kit_color_name
            )
            if len(color_counts) > 1:
                color_totals = sorted(color_counts.values(), reverse=True)
                if color_totals[1] / sum(color_totals) >= 0.15:
                    candidate["ambiguous"] = True
            if candidate["evidence"]:
                candidate["rep_crop_uri"] = candidate["evidence"][0][
                    "thumbnail_uri"
                ]
            if anchor_tracklet_id in active_tracklet_ids:
                anchor_crops = analysis_repository().list_crops(anchor_tracklet_id)
                if anchor_crops:
                    target_ts = (
                        anchor_ts
                        if anchor_ts is not None
                        else (anchor_crops[0].ts + anchor_crops[-1].ts) / 2
                    )
                    anchor_crop = min(
                        anchor_crops,
                        key=lambda item: (abs(item.ts - target_ts), item.crop_id),
                    )
                    anchor_item = evidence_artifact_service().build_candidate_thumbnail(
                        project_id,
                        current_cluster.cluster_id,
                        anchor_crop,
                    )
                    existing_anchor = next(
                        (
                            item
                            for item in candidate["evidence"]
                            if item.get("thumbnail_uri")
                            == anchor_item["thumbnail_uri"]
                        ),
                        None,
                    )
                    if existing_anchor:
                        anchor_item = existing_anchor
                    evidence_limit = max(1, min(12, len(candidate["evidence"])))
                    candidate["evidence"] = [anchor_item] + [
                        item
                        for item in candidate["evidence"]
                        if item.get("tracklet_id") != anchor_tracklet_id
                    ][: evidence_limit - 1]
                    candidate["rep_crop_uri"] = anchor_item["thumbnail_uri"]
        agreement = candidate.get("jersey_agreement", {})
        readings = int(agreement.get("readings", 0))
        agrees = (
            None
            if not project.jersey_hint or not readings
            else candidate.get("jersey_number") == project.jersey_hint
        )
        candidate["jersey_agreement"] = {
            "readings": readings,
            "agrees_with_hint": agrees,
        }
        factor = 1.25 if agrees is True else 0.75 if agrees is False else 1.0
        candidate["rank_score"] = float(candidate.get("screen_time_s", 0)) * factor
    if cluster_id is not None:
        candidates = [
            candidate
            for candidate in candidates
            if candidate["cluster_id"] == cluster_id
        ]
    candidates.sort(
        key=lambda candidate: (
            -float(candidate.get("rank_score", 0)),
            candidate["cluster_id"],
        )
    )
    return {
        "candidates": [
            {key: value for key, value in candidate.items() if key != "rank_score"}
            for candidate in candidates
        ]
    }


@router.put("/{project_id}/jersey-hint")
def put_jersey_hint(
    project_id: str, request: JerseyHintRequest
) -> dict[str, str | None]:
    _project_or_404(project_id)
    project = project_repository().set_jersey_hint(
        project_id, request.jersey_hint
    )
    return {"jersey_hint": project.jersey_hint}


@router.post("/{project_id}/target")
def confirm_target(project_id: str, request: TargetRequest) -> dict:
    _project_or_404(project_id)
    return identity_service().confirm(project_id, request.cluster_id)


@router.delete("/{project_id}/target", status_code=204)
def reset_target(project_id: str) -> Response:
    _project_or_404(project_id)
    identity_service().reset(project_id)
    return Response(status_code=204)


@router.post("/{project_id}/target/adjust")
def adjust_target(project_id: str, request: TargetAdjustRequest) -> dict:
    _project_or_404(project_id)
    return identity_service().adjust(
        project_id,
        add_tracklet_ids=request.add_tracklet_ids,
        remove_tracklet_ids=request.remove_tracklet_ids,
    )


@router.get("/{project_id}/timeline")
def get_timeline(project_id: str) -> dict:
    _project_or_404(project_id)
    return timeline_service().timeline(project_id)


@router.patch("/{project_id}/timeline/{segment_id}")
def patch_timeline_segment(
    project_id: str, segment_id: str, request: TimelineSegmentPatchRequest
) -> dict:
    _project_or_404(project_id)
    try:
        return timeline_service().set_segment(
            project_id,
            segment_id,
            included=request.included,
            start_ts=request.start_ts,
            end_ts=request.end_ts,
        )
    except KeyError as exc:
        raise AppError("That segment is no longer available.", status_code=404) from exc


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str) -> Response:
    _project_or_404(project_id)
    project_repository().delete(project_id)
    cleanup_service().cleanup_project(project_id)
    return Response(status_code=204)


@router.get("/{project_id}/evidence-media/{artifact_name}")
def get_evidence_media(project_id: str, artifact_name: str) -> FileResponse:
    _project_or_404(project_id)
    path = artifact_service().resolve_evidence_path(project_id, artifact_name)
    media_type = "video/mp4" if path.suffix.lower() == ".mp4" else "image/jpeg"
    return FileResponse(path, media_type=media_type)
