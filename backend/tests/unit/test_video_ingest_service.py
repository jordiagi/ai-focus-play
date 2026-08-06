"""Tests for video ingestion service."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.services.video_ingest_service import (
    VideoIngestResult,
    _probe_video,
    _validate_file,
    ingest_video,
)


@pytest.fixture
def sample_mp4(tmp_path: Path) -> str:
    """Create a minimal valid MP4 for testing."""
    mp4 = tmp_path / "test.mp4"
    # Use ffmpeg to create a 1-frame black video with audio if available
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", "color=c=black:s=320x240:d=1:r=30",
                "-f", "lavfi",
                "-i", "aevalsrc=0",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-shortest",
                str(mp4),
            ],
            capture_output=True,
            timeout=30,
        )
        return str(mp4)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pytest.skip("ffmpeg not available for test fixture creation")


@pytest.fixture
def sample_mp4_path(sample_mp4: str | None) -> str | None:
    """Pass-through fixture returning the path to a generated MP4."""
    return sample_mp4


class TestValidateFile:
    def test_nonexistent_file(self):
        err = _validate_file("/nonexistent/video.mp4")
        assert err is not None
        assert "not found" in err.lower()

    def test_directory(self, tmp_path: Path):
        err = _validate_file(str(tmp_path))
        assert err is not None
        assert "not a file" in err.lower()

    def test_too_small_file(self, tmp_path: Path) -> None:
        tiny = tmp_path / "tiny.mp4"
        tiny.write_text("")
        err = _validate_file(str(tiny))
        assert err is not None
        assert "too small" in err.lower()


class TestProbeVideo:
    @patch("subprocess.run")
    def test_valid_probe(self, mock_run: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
                 "r_frame_rate": "30/1"},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "120.5"},
        })
        mock_run.return_value = mock_result

        probe = _probe_video("/path/to/video.mp4")
        assert probe.duration_seconds == 120.5
        assert probe.fps == 30.0
        assert probe.width == 1920
        assert probe.height == 1080
        assert probe.codec == "h264"
        assert probe.audio_codec == "aac"

    @patch("subprocess.run")
    def test_no_video_stream(self, mock_run: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"streams": [{"codec_type": "audio"}], "format": {}})
        mock_run.return_value = mock_result

        result = _probe_video("/path/to/video.mp4")
        assert isinstance(result, ValueError)

    @patch("subprocess.run")
    def test_ffprobe_failure(self, mock_run: MagicMock) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"Invalid file"
        mock_run.return_value = mock_result

        result = _probe_video("/nonexistent.mp4")
        assert isinstance(result, ValueError)


class TestIngestVideo:
    @patch("subprocess.run")
    def test_full_ingestion(self, mock_run: MagicMock, sample_mp4: str | None) -> None:
        if sample_mp4 is None:
            pytest.skip("No ffmpeg fixture available")

        # Mock ffprobe to return valid probe data
        mock_probe = MagicMock()
        mock_probe.returncode = 0
        mock_probe.stdout = json.dumps({
            "streams": [
                {"codec_type": "video", "codec_name": "h264", "width": 320, "height": 240,
                 "r_frame_rate": "30/1"},
                {"codec_type": "audio", "codec_name": "aac"},
            ],
            "format": {"duration": "1.0"},
        })

        mock_frames = MagicMock()
        mock_frames.returncode = 0
        mock_frames.stdout = "\n".join(f"{i / 30:.3f}" for i in range(30))

        def run_side_effect(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            # Frame index uses -select_streams; probe uses -print_format/-show_format
            if "-select_streams" in cmd:
                return mock_frames
            if "ffprobe" in str(cmd):
                return mock_probe
            raise subprocess.CalledProcessError(1, cmd)

        mock_run.side_effect = run_side_effect

        result = ingest_video(sample_mp4)
        assert result.validated is True
        assert result.source_id is not None
        assert result.frame_count > 0

    @patch("subprocess.run")
    def test_corrupted_file(self, mock_run: MagicMock, tmp_path: Path) -> None:
        bad = tmp_path / "corrupt.mp4"
        bad.write_text("not a video file at all")

        result = ingest_video(str(bad))
        assert result.validated is False
        assert result.validation_error is not None
        assert isinstance(result, VideoIngestResult)


class TestFrameCount:
    def test_ingest_result_has_validated_property(self) -> None:
        with_error = VideoIngestResult(
            source_id="s1", file_path="/test.mp4", original_filename="test.mp4",
            stream=MagicMock(), frame_count=0, validation_error="bad file",
        )
        assert with_error.validated is False

        without_error = VideoIngestResult(
            source_id="s1", file_path="/test.mp4", original_filename="test.mp4",
            stream=MagicMock(), frame_count=50,
        )
        assert without_error.validated is True
