from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from src.app.config import Settings
from src.app.errors import AppError
from src.domain.models.detection import TrackletCrop
from src.services.artifact_service import ArtifactService


@dataclass(frozen=True)
class ExtractedEvidenceArtifact:
    sample_type: str
    timestamp_seconds: float
    start_seconds: float
    end_seconds: float
    media_uri: str
    thumbnail_uri: str
    artifact_path: str
    thumbnail_path: str


class EvidenceArtifactService:
    def __init__(self, artifacts: ArtifactService, settings: Settings) -> None:
        self.artifacts = artifacts
        self.settings = settings

    def extract_samples(
        self,
        project_id: str,
        source_path: Path,
        start_seconds: float,
        end_seconds: float,
    ) -> list[ExtractedEvidenceArtifact]:
        if shutil.which("ffmpeg") is None:
            raise AppError("FFmpeg is required to extract real player evidence", status_code=500)
        if not source_path.exists() or not source_path.is_file():
            raise AppError("Real evidence extraction requires an available local source video", status_code=409)

        duration = self._bounded_duration(source_path, start_seconds, end_seconds)
        window_end = start_seconds + duration
        timestamps = self._sample_timestamps(start_seconds, duration)
        artifacts: list[ExtractedEvidenceArtifact] = []
        for index, timestamp in enumerate(timestamps, start=1):
            artifacts.append(self._extract_at(project_id, source_path, index, timestamp, window_end))
        return artifacts

    def build_candidate_evidence(
        self,
        project_id: str,
        source_path: Path,
        cluster_id: str,
        crops: Sequence[TrackletCrop],
    ) -> list[dict]:
        if shutil.which("ffmpeg") is None:
            raise AppError("FFmpeg is required to prepare player evidence", status_code=500)
        if not source_path.is_file():
            raise AppError("The source video is not available for player evidence", status_code=409)

        results: list[dict] = []
        clip_seconds = max(1, self.settings.evidence_clip_seconds)
        for index, crop in enumerate(crops):
            token = sha1(f"{cluster_id}:{crop.crop_id}".encode()).hexdigest()[:16]
            clip_name = f"candidate-{token}.mp4"
            item = self.build_candidate_thumbnail(project_id, cluster_id, crop)
            if index < 2:
                clip_path = self.artifacts.create_evidence_path(
                    project_id, clip_name
                )
                if not clip_path.is_file():
                    clip_start = max(0.0, crop.ts - clip_seconds / 2)
                    self._run_ffmpeg(
                        [
                            "ffmpeg",
                            "-y",
                            "-loglevel",
                            "error",
                            "-ss",
                            f"{clip_start:.3f}",
                            "-t",
                            f"{clip_seconds:.3f}",
                            "-i",
                            str(source_path),
                            "-vf",
                            "scale=960:-2",
                            "-an",
                            "-movflags",
                            "+faststart",
                            str(clip_path),
                        ]
                    )
                item["clip_uri"] = self.artifacts.evidence_media_uri(
                    project_id, clip_name
                )
            results.append(item)
        return results

    def build_candidate_thumbnail(
        self,
        project_id: str,
        cluster_id: str,
        crop: TrackletCrop,
    ) -> dict:
        token = sha1(f"{cluster_id}:{crop.crop_id}".encode()).hexdigest()[:16]
        thumbnail_name = f"candidate-{token}.jpg"
        thumbnail_path = self.artifacts.create_evidence_path(
            project_id, thumbnail_name
        )
        crop_path = Path(crop.crop_path)
        if not thumbnail_path.is_file():
            if not crop_path.is_file():
                raise AppError("A player evidence crop is missing", status_code=409)
            shutil.copyfile(crop_path, thumbnail_path)
        return {
            "ts": crop.ts,
            "thumbnail_uri": self.artifacts.evidence_media_uri(
                project_id, thumbnail_name
            ),
            "tracklet_id": crop.tracklet_id,
        }

    def _bounded_duration(self, source_path: Path, start_seconds: float, end_seconds: float) -> float:
        if end_seconds > start_seconds:
            return max(1.0, end_seconds - start_seconds)
        probed = self._probe_duration(source_path)
        return max(1.0, probed - start_seconds if probed > start_seconds else probed)

    def _probe_duration(self, source_path: Path) -> float:
        if shutil.which("ffprobe") is None:
            return 7200.0
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AppError("Source video could not be read for evidence extraction", status_code=422)
        try:
            return float(result.stdout.strip())
        except ValueError as exc:
            raise AppError("Source video duration could not be read", status_code=422) from exc

    def _sample_timestamps(self, start_seconds: float, duration: float) -> list[float]:
        count = max(1, self.settings.evidence_sample_count)
        fractions = [0.18, 0.42, 0.67, 0.82, 0.93]
        if count > len(fractions):
            fractions.extend((index + 1) / (count + 1) for index in range(count - len(fractions)))
        timestamps = [start_seconds + duration * fraction for fraction in fractions[:count]]
        return [round(max(0.0, timestamp), 3) for timestamp in timestamps]

    def _extract_at(
        self,
        project_id: str,
        source_path: Path,
        index: int,
        timestamp: float,
        window_end: float,
    ) -> ExtractedEvidenceArtifact:
        token = uuid4().hex[:10]
        thumbnail_name = f"evidence-{index}-{token}.jpg"
        clip_name = f"evidence-{index}-{token}.mp4"
        thumbnail_path = self.artifacts.create_evidence_path(project_id, thumbnail_name)
        clip_path = self.artifacts.create_evidence_path(project_id, clip_name)
        clip_seconds = max(1, self.settings.evidence_clip_seconds)
        clip_start = max(0.0, timestamp - (clip_seconds / 2))
        clip_end = min(max(window_end, clip_start + 0.5), clip_start + clip_seconds)

        self._run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(source_path),
                "-frames:v",
                "1",
                "-vf",
                "scale=640:-2",
                str(thumbnail_path),
            ]
        )
        self._run_ffmpeg(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-ss",
                f"{clip_start:.3f}",
                "-t",
                f"{max(0.5, clip_end - clip_start):.3f}",
                "-i",
                str(source_path),
                "-vf",
                "scale=960:-2",
                "-an",
                "-movflags",
                "+faststart",
                str(clip_path),
            ]
        )
        return ExtractedEvidenceArtifact(
            sample_type="clip",
            timestamp_seconds=timestamp,
            start_seconds=round(clip_start, 3),
            end_seconds=round(clip_end, 3),
            media_uri=self.artifacts.evidence_media_uri(project_id, clip_name),
            thumbnail_uri=self.artifacts.evidence_media_uri(project_id, thumbnail_name),
            artifact_path=str(clip_path),
            thumbnail_path=str(thumbnail_path),
        )

    def _run_ffmpeg(self, command: list[str]) -> None:
        try:
            subprocess.run(command, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise AppError("Evidence media extraction failed", status_code=500) from exc
