"""Video ingestion: validate and probe a source video without scanning every frame."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

@dataclass
class StreamProbe:
    duration_seconds: float
    fps: float
    width: int
    height: int
    codec: str
    audio_codec: str


@dataclass
class VideoIngestResult:
    source_id: str
    file_path: str
    original_filename: str
    stream: StreamProbe
    frame_count: int
    validation_error: str | None = None

    @property
    def validated(self) -> bool:
        return self.validation_error is None


def _probe_video(file_path: str) -> StreamProbe | ValueError:
    """Run ffprobe to extract stream metadata."""
    probe_cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return ValueError(f"ffprobe unavailable or timed out: {exc}")

    if result.returncode != 0:
        return ValueError(f"ffprobe failed: {result.stderr.strip()}")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        return ValueError("No video stream found in file")

    # Find audio stream if present
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    fmt = data.get("format", {})

    codec = video_stream.get("codec_name", "")
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))

    # FPS: try r_frame_rate first, then avg_frame_rate
    fps_str = video_stream.get("r_frame_rate") or video_stream.get("avg_frame_rate", "0/1")
    num, den = map(int, fps_str.split("/")) if "/" in fps_str else (fps_str, 1)
    fps = num / den if den else 0.0

    audio_codec = audio_stream.get("codec_name", "") if audio_stream else ""
    duration = float(fmt.get("duration", 0)) if fmt.get("duration") else 0.0

    return StreamProbe(
        duration_seconds=round(duration, 3),
        fps=round(fps, 3),
        width=width,
        height=height,
        codec=codec,
        audio_codec=audio_codec,
    )


def _validate_file(file_path: str) -> str | None:
    """Check that the file exists and is readable."""
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    if not path.is_file():
        return f"Not a file: {file_path}"
    if not os.access(file_path, os.R_OK):
        return f"File not readable: {file_path}"
    if path.stat().st_size < 1024:
        return "File too small to be a valid video"
    return None


def ingest_video(
    file_path: str,
    original_filename: str = "",
) -> VideoIngestResult:
    """Ingest a video file by validating it and probing stream metadata.

    Returns VideoIngestResult with validation_error set on failure.
    """
    source_id = str(uuid4())
    if not original_filename:
        original_filename = Path(file_path).name

    # Validate file accessibility
    val_err = _validate_file(file_path)
    if val_err:
        return VideoIngestResult(
            source_id=source_id,
            file_path=file_path,
            original_filename=original_filename,
            stream=StreamProbe(duration_seconds=0, fps=0, width=0, height=0, codec="", audio_codec=""),
            frame_count=0,
            validation_error=val_err,
        )

    # Probe stream
    probe = _probe_video(file_path)
    if isinstance(probe, ValueError):
        return VideoIngestResult(
            source_id=source_id,
            file_path=file_path,
            original_filename=original_filename,
            stream=StreamProbe(duration_seconds=0, fps=0, width=0, height=0, codec="", audio_codec=""),
            frame_count=0,
            validation_error=str(probe),
        )

    return VideoIngestResult(
        source_id=source_id,
        file_path=file_path,
        original_filename=original_filename,
        stream=probe,
        frame_count=round(probe.duration_seconds * probe.fps),
    )


def validate_video(file_path: str) -> tuple[bool, str | None]:
    """Return (is_valid, error_message)."""
    err = _validate_file(file_path)
    if err:
        return False, err
    probe = _probe_video(file_path)
    if isinstance(probe, ValueError):
        return False, str(probe)
    return True, None
