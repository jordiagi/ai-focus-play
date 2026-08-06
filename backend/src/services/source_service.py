from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

from src.app.errors import AppError
from src.app.logging import log_event
from src.domain.models.project import AnalysisProject, utcnow
from src.domain.models.source import VideoSource
from src.services.source_catalog_service import SourceCatalogService
from src.storage.project_repository import ProjectRepository


DEFAULT_DURATION_SECONDS = 7200.0


class SourceService:
    def __init__(self, repository: ProjectRepository, video_root: Path | None = None) -> None:
        self.repository = repository
        self.video_root = video_root or Path("video")

    def attach_source(self, project: AnalysisProject, source_type: str, source_uri: str, display_name: str | None) -> VideoSource:
        source_path, source_reference, relative_path = self._resolve_source(source_type, source_uri)
        duration_seconds = self._probe_duration(str(source_path))
        source = VideoSource(
            source_id=str(uuid4()),
            source_type=source_type,
            display_name=display_name or self._display_name(source_type, source_uri),
            original_uri=str(source_path),
            source_reference=source_reference,
            relative_path=relative_path,
            duration_seconds=duration_seconds,
            access_status="available",
            ingest_status="ready",
        )
        self.repository.save_source(source)
        project.source_id = source.source_id
        project.status = "source_ready"
        project.workflow_step = "confirm_player"
        project.updated_at = utcnow()
        self.repository.save_project(project)
        log_event("source_attached", project_id=project.project_id, source_id=source.source_id)
        return source

    def _resolve_source(self, source_type: str, source_uri: str) -> tuple[Path, str, str | None]:
        if source_type in {"discovered_local", "relative_local_path"}:
            path = SourceCatalogService(self.video_root).resolve_relative_video(source_uri)
            return path, source_uri, SourceCatalogService(self.video_root).relative_path_for(path)
        if source_type == "youtube":
            if not ("youtube.com" in source_uri or "youtu.be" in source_uri):
                raise AppError("Enter a valid YouTube video link", status_code=400)
            return Path(source_uri), source_uri, None
        return Path(source_uri), source_uri, None

    def _display_name(self, source_type: str, source_uri: str) -> str:
        if source_type == "youtube":
            return "YouTube match"
        return Path(source_uri).name or "video-source"

    def _probe_duration(self, source_uri: str) -> float:
        source_path = Path(source_uri)
        if not source_path.exists() or shutil.which("ffprobe") is None:
            return DEFAULT_DURATION_SECONDS
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "json",
                    str(source_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return DEFAULT_DURATION_SECONDS
            payload = json.loads(result.stdout)
            return float(payload.get("format", {}).get("duration", DEFAULT_DURATION_SECONDS))
        except (OSError, TypeError, ValueError):
            return DEFAULT_DURATION_SECONDS
