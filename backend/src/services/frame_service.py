from __future__ import annotations

import subprocess
from pathlib import Path

from src.app.config import Settings
from src.app.errors import AppError
from src.domain.models.video import SourceVideo
from src.services.artifact_service import ArtifactService


class FrameService:
    def __init__(self, artifacts: ArtifactService, settings: Settings) -> None:
        self.artifacts = artifacts
        self.settings = settings

    def get_frame(self, project_id: str, source: SourceVideo, timestamp: float) -> Path:
        if source.proxy_status != "ready" or not source.proxy_path:
            raise AppError(
                "We're still getting the video ready — try again in a moment.",
                status_code=409,
            )
        if timestamp < 0 or (
            source.duration_s is not None and timestamp > source.duration_s
        ):
            raise AppError("That moment is outside the video — choose another time.", status_code=400)
        frames_dir = self.artifacts.frames_dir(project_id)
        path = frames_dir / f"frame_{round(timestamp * 1000):010d}.jpg"
        if not path.exists():
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-loglevel",
                    "error",
                    "-ss",
                    f"{timestamp:.3f}",
                    "-i",
                    source.proxy_path,
                    "-frames:v",
                    "1",
                    "-q:v",
                    "2",
                    str(path),
                ],
                capture_output=True,
            )
            if result.returncode != 0 or not path.exists():
                raise AppError(
                    "We couldn't show that frame. Your video is safe — try another moment.",
                    status_code=500,
                )
        path.touch()
        self._prune(frames_dir, keep=path)
        return path

    def _prune(self, frames_dir: Path, *, keep: Path) -> None:
        files = sorted(
            (path for path in frames_dir.glob("frame_*.jpg") if path != keep),
            key=lambda path: path.stat().st_mtime,
        )
        overflow = max(0, len(files) + 1 - self.settings.frames_cache_max)
        for path in files[:overflow]:
            path.unlink(missing_ok=True)
