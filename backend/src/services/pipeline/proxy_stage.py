from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Protocol

from src.app.config import get_settings
from src.services.artifact_service import ArtifactService
from src.storage.db import Database
from src.storage.job_repository import JobRepository
from src.storage.project_repository import ProjectRepository
from src.storage.source_repository import SourceRepository


class ProgressContext(Protocol):
    job_id: str
    cancelled: bool

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None: ...


def run_proxy_stage(context: ProgressContext, _: dict[str, Any]) -> None:
    settings = get_settings()
    database = Database(settings.db_path)
    job = JobRepository(database).get(context.job_id)
    project = ProjectRepository(database).get(job.project_id)
    if not project.source_id:
        raise RuntimeError("Project has no source video")
    sources = SourceRepository(database)
    source = sources.get(project.source_id)
    artifacts = ArtifactService(settings)
    source_path = artifacts.resolve_source_path(project.project_id, source.file_path)
    if str(source_path) != source.file_path:
        source.file_path = str(source_path)
        sources.save(source)
    output = artifacts.proxy_path(project.project_id)
    temporary = output.with_suffix(".tmp.mp4")
    temporary.unlink(missing_ok=True)
    context.update(0, "Getting the video ready")
    succeeded = _transcode(
        context,
        source_path,
        temporary,
        float(source.duration_s or 0),
        encoder="h264_videotoolbox",
    )
    if not succeeded and not context.cancelled:
        temporary.unlink(missing_ok=True)
        succeeded = _transcode(
            context,
            source_path,
            temporary,
            float(source.duration_s or 0),
            encoder="libx264",
        )
    if context.cancelled:
        temporary.unlink(missing_ok=True)
        return
    if not succeeded or not temporary.exists():
        sources.update_proxy(source.source_id, proxy_path=None, proxy_status="failed")
        raise RuntimeError("FFmpeg could not create the proxy video")
    shutil.move(str(temporary), output)
    sources.update_proxy(
        source.source_id, proxy_path=str(output), proxy_status="ready"
    )
    context.update(100, "Getting the video ready — done")


def _transcode(
    context: ProgressContext,
    source: Path,
    output: Path,
    duration_s: float,
    *,
    encoder: str,
) -> bool:
    codec_args = (
        ["-c:v", encoder, "-b:v", "2500k"]
        if encoder == "h264_videotoolbox"
        else ["-c:v", encoder, "-crf", "27", "-preset", "veryfast"]
    )
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vf",
        "scale=-2:720",
        *codec_args,
        "-g",
        "30",
        "-an",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output),
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    for line in process.stdout:
        if context.cancelled:
            process.terminate()
            break
        key, _, value = line.strip().partition("=")
        if key in {"out_time_us", "out_time_ms"} and duration_s > 0:
            try:
                processed_s = float(value) / 1_000_000
            except ValueError:
                continue
            progress = min(99.0, 100.0 * processed_s / duration_s)
            context.update(progress, "Getting the video ready")
    return process.wait() == 0
