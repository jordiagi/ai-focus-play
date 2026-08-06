import shutil
import subprocess
from pathlib import Path

import pytest

from src.app.config import get_settings
from src.domain.models.detection import TrackletCrop
from src.services.artifact_service import ArtifactService
from src.services.evidence_artifact_service import EvidenceArtifactService


def _make_video(path: Path, duration: float = 2.0) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=15",
            "-t",
            str(duration),
            str(path),
        ],
        check=True,
        capture_output=True,
    )


@pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="ffmpeg and ffprobe required")
def test_evidence_artifact_service_extracts_real_frame_and_clip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("AI_FOCUS_EVIDENCE_SAMPLE_COUNT", "2")
    monkeypatch.setenv("AI_FOCUS_EVIDENCE_CLIP_SECONDS", "1")
    source = tmp_path / "source.mp4"
    _make_video(source)

    service = EvidenceArtifactService(ArtifactService(get_settings()), get_settings())
    samples = service.extract_samples("p1", source, 0, 2)

    assert len(samples) == 2
    for sample in samples:
        assert sample.media_uri.startswith("/projects/p1/evidence-media/")
        assert sample.thumbnail_uri.startswith("/projects/p1/evidence-media/")
        assert Path(sample.artifact_path).exists()
        assert Path(sample.thumbnail_path).exists()
        assert 0 <= sample.timestamp_seconds <= 2


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg required",
)
def test_candidate_evidence_reuses_crop_and_preview_clip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AI_FOCUS_DATA_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setenv("AI_FOCUS_EVIDENCE_CLIP_SECONDS", "1")
    source = tmp_path / "source.mp4"
    crop_path = tmp_path / "crop.jpg"
    _make_video(source)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-ss",
            "0.5",
            "-i",
            str(source),
            "-frames:v",
            "1",
            str(crop_path),
        ],
        check=True,
        capture_output=True,
    )
    service = EvidenceArtifactService(ArtifactService(get_settings()), get_settings())
    crop = TrackletCrop(
        crop_id="c1",
        tracklet_id="t1",
        ts=0.5,
        crop_path=str(crop_path),
    )

    first = service.build_candidate_evidence(
        "p1", source, "cluster-1", [crop]
    )
    second = service.build_candidate_evidence(
        "p1", source, "cluster-1", [crop]
    )

    assert first == second
    assert first[0]["tracklet_id"] == "t1"
    evidence_dir = tmp_path / "artifacts" / "p1" / "evidence"
    assert len(list(evidence_dir.glob("candidate-*.jpg"))) == 1
    assert len(list(evidence_dir.glob("candidate-*.mp4"))) == 1
