from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Protocol

from src.app.config import get_settings
from src.app.logging import log_event
from src.domain.models.selection import AppearanceSegment
from src.services.artifact_service import ArtifactService
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.output_repository import OutputRepository
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository

# Fixed render size. The proxy is 720p and detection boxes are normalized, so we
# can map normalized boxes to pixels with a known canvas.
_OUT_W = 1280
_OUT_H = 720


class ProgressContext(Protocol):
    job_id: str
    cancelled: bool

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None: ...


def run_export_stage(context: ProgressContext, params: dict[str, Any]) -> None:
    settings = get_settings()
    database = Database(settings.db_path)
    jobs_params = params or {}
    outputs = OutputRepository(database)

    output_id = jobs_params.get("output_id")
    if not output_id:
        # params may be empty when re-dispatched; recover from the job row.
        from src.storage.job_repository import JobRepository

        job = JobRepository(database).get(context.job_id)
        output_id = job.params.get("output_id")
    if not output_id:
        raise ValueError("export stage requires an output_id parameter")

    output = outputs.get(output_id)
    project = ProjectRepository(database).get(output.project_id)
    source = SourceRepository(database).get_for_project(project.project_id)
    if source is None:
        raise ValueError("export stage requires an attached source video")

    analysis = AnalysisRepository(database)
    selection = SelectionRepository(database)
    artifacts = ArtifactService(settings)

    if shutil.which("ffmpeg") is None:
        raise RuntimeError("FFmpeg is required to render reels")

    output.status = "rendering"
    outputs.save(output)
    context.update(2.0, "Getting your reel ready")

    segments = _segments_for_output(selection, output.segment_ids, project.project_id)
    if not segments:
        raise RuntimeError("There are no included appearances to put in this reel yet.")

    target_tracklet_ids = _target_tracklet_ids(analysis, source.source_id, project.target_cluster_id)
    source_path = artifacts.resolve_source_path(project.project_id, source.file_path)
    export_path = artifacts.create_export_path(project.project_id, output.output_id)
    work_dir = export_path.parent
    work_dir.mkdir(parents=True, exist_ok=True)

    segment_paths: list[Path] = []
    total = len(segments)
    for index, segment in enumerate(segments):
        if context.cancelled:
            return
        segment_path = work_dir / f"{output.output_id}-seg-{index:04d}.mp4"
        sendcmd_path = None
        if output.overlay_mode == "target_marker":
            sendcmd_path = _write_marker_script(
                work_dir,
                output.output_id,
                index,
                analysis,
                source.source_id,
                target_tracklet_ids,
                segment,
            )
        _render_segment(source_path, segment_path, segment, sendcmd_path)
        segment_paths.append(segment_path)
        context.update(
            5.0 + 85.0 * (index + 1) / total,
            f"Cutting clip {index + 1} of {total}",
            {"segments_rendered": index + 1},
        )

    context.update(92.0, "Stitching your reel together")
    _concat(work_dir, output.output_id, segment_paths, export_path)
    for path in segment_paths:
        path.unlink(missing_ok=True)
    for leftover in work_dir.glob(f"{output.output_id}-*.txt"):
        leftover.unlink(missing_ok=True)

    duration = sum(max(0.0, s.end_ts - s.start_ts) for s in segments)
    output.status = "ready"
    output.file_path = str(export_path)
    output.duration_s = round(duration, 3)
    outputs.save(output)
    context.update(100.0, "Your reel is ready to download")
    log_event(
        "export_finished",
        project_id=project.project_id,
        output_id=output.output_id,
        duration_s=output.duration_s,
        segment_count=total,
    )


def _segments_for_output(
    selection: SelectionRepository, segment_ids: list[str], project_id: str
) -> list[AppearanceSegment]:
    by_id = {s.segment_id: s for s in selection.list_segments(project_id)}
    chosen = [by_id[sid] for sid in segment_ids if sid in by_id]
    return sorted(chosen, key=lambda s: s.start_ts)


def _target_tracklet_ids(
    analysis: AnalysisRepository, source_id: str, cluster_id: str | None
) -> set[str]:
    if not cluster_id:
        return set()
    return {
        tracklet.tracklet_id
        for tracklet in analysis.list_tracklets(source_id)
        if tracklet.cluster_id == cluster_id
        and tracklet.cluster_assignment != "user_removed"
    }


def _write_marker_script(
    work_dir: Path,
    output_id: str,
    index: int,
    analysis: AnalysisRepository,
    source_id: str,
    tracklet_ids: set[str],
    segment: AppearanceSegment,
) -> Path | None:
    detections = [
        detection
        for detection in analysis.detections_in_range(
            source_id, segment.start_ts, segment.end_ts
        )
        if detection.tracklet_id in tracklet_ids
    ]
    if not detections:
        return None
    lines: list[str] = []
    for detection in detections:
        rel = max(0.0, detection.ts - segment.start_ts)
        x_px = max(0.0, detection.x) * _OUT_W
        y_px = max(0.0, detection.y) * _OUT_H
        w_px = max(1.0, detection.w * _OUT_W)
        h_px = max(1.0, detection.h * _OUT_H)
        lines.append(f"{rel:.3f} drawbox x {x_px:.1f};")
        lines.append(f"{rel:.3f} drawbox y {y_px:.1f};")
        lines.append(f"{rel:.3f} drawbox w {w_px:.1f};")
        lines.append(f"{rel:.3f} drawbox h {h_px:.1f};")
    script_path = work_dir / f"{output_id}-marker-{index:04d}.txt"
    script_path.write_text("\n".join(lines) + "\n")
    return script_path


def _render_segment(
    source_path: Path,
    segment_path: Path,
    segment: AppearanceSegment,
    sendcmd_path: Path | None,
) -> None:
    start = max(0.0, float(segment.start_ts))
    duration = max(0.5, float(segment.end_ts) - start)
    video_filter = f"scale={_OUT_W}:{_OUT_H}"
    if sendcmd_path is not None:
        # Escape the path for the filtergraph, then let sendcmd drive drawbox.
        escaped = str(sendcmd_path).replace("\\", "\\\\").replace(":", "\\:")
        video_filter += (
            f",sendcmd=f='{escaped}',"
            "drawbox=x=0:y=0:w=0:h=0:color=yellow@0.9:thickness=4"
        )
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source_path),
        "-vf",
        video_filter,
        "-an",
        "-movflags",
        "+faststart",
        str(segment_path),
    ]
    subprocess.run(command, check=True, capture_output=True)


def _concat(
    work_dir: Path, output_id: str, segment_paths: list[Path], export_path: Path
) -> None:
    if len(segment_paths) == 1:
        segment_paths[0].replace(export_path)
        return
    concat_file = work_dir / f"{output_id}-concat.txt"
    concat_file.write_text("".join(f"file '{path}'\n" for path in segment_paths))
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(export_path),
    ]
    subprocess.run(command, check=True, capture_output=True)
    concat_file.unlink(missing_ok=True)
