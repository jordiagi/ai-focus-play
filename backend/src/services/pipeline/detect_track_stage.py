from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol, Sequence

from src.app.config import Settings, get_settings
from src.domain.models.detection import Detection, Tracklet, TrackletCrop
from src.domain.models.video import SourceVideo
from src.ml.interfaces import DetectionBox, Detector, FrameInput
from src.services.artifact_service import ArtifactService
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.job_repository import JobRepository
from src.storage.project_repository import ProjectRepository
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository


class ProgressContext(Protocol):
    job_id: str
    cancelled: bool

    def update(
        self, progress_pct: float, message: str, checkpoint: dict | None = None
    ) -> None: ...


@dataclass(frozen=True)
class TrackedDetection:
    tracker_id: int
    box: DetectionBox


class Tracker(Protocol):
    def update(
        self, detections: Sequence[DetectionBox]
    ) -> list[TrackedDetection]: ...


FrameStreamer = Callable[[Path, int, int, float, float], Iterable[FrameInput]]
CropWriter = Callable[[FrameInput, DetectionBox, Path], tuple[float, int]]


@dataclass
class _TrackletState:
    tracklet_id: str
    source_id: str
    start_ts: float
    end_ts: float
    frame_count: int
    confidence_sum: float

    @classmethod
    def from_existing(cls, tracklet: Tracklet) -> "_TrackletState":
        return cls(
            tracklet_id=tracklet.tracklet_id,
            source_id=tracklet.source_id,
            start_ts=tracklet.start_ts,
            end_ts=tracklet.end_ts,
            frame_count=tracklet.frame_count,
            confidence_sum=float(tracklet.avg_conf or 0) * tracklet.frame_count,
        )

    def observe(self, ts: float, confidence: float) -> None:
        self.start_ts = min(self.start_ts, ts)
        self.end_ts = max(self.end_ts, ts)
        self.frame_count += 1
        self.confidence_sum += confidence

    def model(self) -> Tracklet:
        return Tracklet(
            tracklet_id=self.tracklet_id,
            source_id=self.source_id,
            start_ts=self.start_ts,
            end_ts=self.end_ts,
            frame_count=self.frame_count,
            avg_conf=self.confidence_sum / self.frame_count,
        )


class DetectTrackStage:
    def __init__(
        self,
        *,
        settings: Settings,
        database: Database,
        detector: Detector,
        tracker_factory: Callable[[], Tracker],
        crop_writer: CropWriter | None = None,
        checkpoint_every: int = 1_000,
        batch_size: int = 8,
        frame_streamer: FrameStreamer | None = None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.detector = detector
        self.tracker_factory = tracker_factory
        self.crop_writer = crop_writer or write_jpeg_crop
        self.checkpoint_every = max(1, checkpoint_every)
        self.batch_size = max(1, batch_size)
        self.frame_streamer = frame_streamer or stream_raw_frames
        self.analysis = AnalysisRepository(database)
        self.selection = SelectionRepository(database)
        self.artifacts = ArtifactService(settings)

    def process(
        self,
        context: ProgressContext,
        project_id: str,
        source: SourceVideo,
        *,
        checkpoint: dict[str, Any],
    ) -> None:
        if not source.width or not source.height:
            raise RuntimeError("Source dimensions are required for player detection")
        last_checkpoint_ts = float(checkpoint.get("last_ts", -1.0))
        seek_ts = max(0.0, last_checkpoint_ts - 5.0)
        tracker_session = round(seek_ts * 1_000)
        tracker = self.tracker_factory()
        states: dict[str, _TrackletState] = {}
        last_crop_ts = self._latest_crop_times(source.source_id)
        pending_detections: list[Detection] = []
        pending_crops: list[TrackletCrop] = []
        persisted_frames = 0
        last_persisted_ts: float | None = None
        batch: list[FrameInput] = []

        source_path = self.artifacts.resolve_source_path(project_id, source.file_path)
        frames = self.frame_streamer(
            source_path,
            int(source.width),
            int(source.height),
            self.settings.analysis_fps,
            seek_ts,
        )
        for frame in frames:
            if context.cancelled:
                break
            batch.append(frame)
            if len(batch) < self.batch_size:
                continue
            persisted_frames, last_persisted_ts = self._process_batch(
                batch,
                tracker,
                project_id,
                source,
                tracker_session,
                last_checkpoint_ts,
                states,
                last_crop_ts,
                pending_detections,
                pending_crops,
                persisted_frames,
                last_persisted_ts,
                context,
            )
            batch = []
            if context.cancelled:
                break
        if batch and not context.cancelled:
            persisted_frames, last_persisted_ts = self._process_batch(
                batch,
                tracker,
                project_id,
                source,
                tracker_session,
                last_checkpoint_ts,
                states,
                last_crop_ts,
                pending_detections,
                pending_crops,
                persisted_frames,
                last_persisted_ts,
                context,
            )
        if context.cancelled and hasattr(frames, "close"):
            frames.close()
        needs_final_checkpoint = (
            last_persisted_ts is not None
            and persisted_frames % self.checkpoint_every != 0
        )
        if needs_final_checkpoint:
            self._checkpoint(
                context,
                project_id,
                source,
                states,
                pending_detections,
                pending_crops,
                last_persisted_ts,
            )

    def _process_batch(
        self,
        frames: list[FrameInput],
        tracker: Tracker,
        project_id: str,
        source: SourceVideo,
        tracker_session: int,
        last_checkpoint_ts: float,
        states: dict[str, _TrackletState],
        last_crop_ts: dict[str, float],
        pending_detections: list[Detection],
        pending_crops: list[TrackletCrop],
        persisted_frames: int,
        last_persisted_ts: float | None,
        context: ProgressContext,
    ) -> tuple[int, float | None]:
        detected = self.detector.detect(frames)
        if len(detected) != len(frames):
            raise RuntimeError("Detector returned a different number of frame results")
        for frame, boxes in zip(frames, detected):
            tracked = tracker.update(boxes)
            if frame.ts <= last_checkpoint_ts + 1e-6:
                continue
            for box, tracker_id in _assign_track_ids(boxes, tracked):
                tracklet_id = (
                    f"{source.source_id}-{tracker_session:010d}-{tracker_id:06d}"
                    if tracker_id is not None
                    else None
                )
                x = _clamp(box.x)
                y = _clamp(box.y)
                pending_detections.append(
                    Detection(
                        source_id=source.source_id,
                        tracklet_id=tracklet_id,
                        ts=frame.ts,
                        x=x,
                        y=y,
                        w=min(_clamp(box.w), 1.0 - x),
                        h=min(_clamp(box.h), 1.0 - y),
                        conf=box.confidence,
                    )
                )
                if tracklet_id is None:
                    continue
                state = states.get(tracklet_id)
                if state is None:
                    state = self._load_state(tracklet_id, source.source_id, frame.ts)
                    states[tracklet_id] = state
                state.observe(frame.ts, box.confidence)
                previous_crop = last_crop_ts.get(tracklet_id)
                if previous_crop is None or frame.ts - previous_crop >= self.settings.crop_interval_s - 1e-6:
                    crop_id = f"{tracklet_id}-{round(frame.ts * 1_000):010d}"
                    crop_path = self.artifacts.crops_dir(
                        project_id, tracklet_id
                    ) / f"{crop_id}.jpg"
                    sharpness, bbox_h_px = self.crop_writer(frame, box, crop_path)
                    pending_crops.append(
                        TrackletCrop(
                            crop_id=crop_id,
                            tracklet_id=tracklet_id,
                            ts=frame.ts,
                            crop_path=str(crop_path),
                            sharpness=sharpness,
                            bbox_h_px=bbox_h_px,
                        )
                    )
                    last_crop_ts[tracklet_id] = frame.ts
            persisted_frames += 1
            last_persisted_ts = frame.ts
            if persisted_frames % self.checkpoint_every == 0:
                self._checkpoint(
                    context,
                    project_id,
                    source,
                    states,
                    pending_detections,
                    pending_crops,
                    frame.ts,
                )
                if context.cancelled:
                    break
        return persisted_frames, last_persisted_ts

    def _checkpoint(
        self,
        context: ProgressContext,
        project_id: str,
        source: SourceVideo,
        states: dict[str, _TrackletState],
        detections: list[Detection],
        crops: list[TrackletCrop],
        last_ts: float,
    ) -> None:
        self.analysis.bulk_upsert_tracklets(state.model() for state in states.values())
        self.analysis.bulk_insert_detections(detections)
        self.analysis.bulk_insert_crops(crops)
        detections.clear()
        crops.clear()
        self._resolve_pins(project_id, source.source_id, last_ts)
        duration = max(float(source.duration_s or 0), last_ts, 0.001)
        watched_minutes = last_ts / 60.0
        total_minutes = duration / 60.0
        context.update(
            min(99.0, 100.0 * last_ts / duration),
            f"Finding every player — watched {watched_minutes:.1f} of {total_minutes:.1f} min",
            {"last_ts": last_ts, "tracker_state": None},
        )

    def _load_state(
        self, tracklet_id: str, source_id: str, ts: float
    ) -> _TrackletState:
        try:
            return _TrackletState.from_existing(self.analysis.get_tracklet(tracklet_id))
        except KeyError:
            return _TrackletState(tracklet_id, source_id, ts, ts, 0, 0.0)

    def _latest_crop_times(self, source_id: str) -> dict[str, float]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.tracklet_id, MAX(c.ts) AS ts
                FROM tracklet_crops c
                JOIN tracklets t ON t.tracklet_id = c.tracklet_id
                WHERE t.source_id = ? GROUP BY c.tracklet_id
                """,
                (source_id,),
            ).fetchall()
        return {row["tracklet_id"]: float(row["ts"]) for row in rows}

    def _resolve_pins(self, project_id: str, source_id: str, last_ts: float) -> None:
        for click in self.selection.list_clicks(project_id, status="pinned"):
            if click.ts > last_ts + 0.5:
                continue
            hits = [
                detection
                for detection in self.analysis.detections_near(source_id, click.ts)
                if detection.x <= click.x_norm <= detection.x + detection.w
                and detection.y <= click.y_norm <= detection.y + detection.h
                and detection.tracklet_id
            ]
            if not hits:
                continue
            hit = min(hits, key=lambda detection: detection.w * detection.h)
            self.selection.update_click_status(
                click.click_id,
                "resolved",
                resolved_tracklet_id=hit.tracklet_id,
            )


class ByteTrackAdapter:
    def __init__(self, *, frame_rate: float = 30.0) -> None:
        import supervision as sv

        self.tracker = sv.ByteTrack(frame_rate=max(1, round(frame_rate)))

    def update(
        self, detections: Sequence[DetectionBox]
    ) -> list[TrackedDetection]:
        import numpy as np
        import supervision as sv

        if not detections:
            self.tracker.update_with_detections(sv.Detections.empty())
            return []
        scale = 1_000.0
        values = np.array(
            [
                [
                    box.x * scale,
                    box.y * scale,
                    (box.x + box.w) * scale,
                    (box.y + box.h) * scale,
                ]
                for box in detections
            ],
            dtype=np.float32,
        )
        tracked = self.tracker.update_with_detections(
            sv.Detections(
                xyxy=values,
                confidence=np.array(
                    [box.confidence for box in detections], dtype=np.float32
                ),
                class_id=np.zeros(len(detections), dtype=int),
            )
        )
        results = []
        for xyxy, confidence, tracker_id in zip(
            tracked.xyxy,
            tracked.confidence,
            tracked.tracker_id,
        ):
            if tracker_id is None:
                continue
            x1, y1, x2, y2 = (float(value) / scale for value in xyxy)
            results.append(
                TrackedDetection(
                    int(tracker_id),
                    DetectionBox(
                        x=x1,
                        y=y1,
                        w=x2 - x1,
                        h=y2 - y1,
                        confidence=float(confidence),
                    ),
                )
            )
        return results


def stream_raw_frames(
    source: Path,
    width: int,
    height: int,
    fps: float,
    start_ts: float,
) -> Iterable[FrameInput]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start_ts:.6f}",
        "-i",
        str(source),
        "-vf",
        f"fps={fps}",
        "-pix_fmt",
        "rgb24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.stdout is not None
    frame_size = width * height * 3
    frame_index = 0
    exhausted = False
    try:
        while True:
            data = _read_exact(process.stdout, frame_size)
            if len(data) != frame_size:
                exhausted = True
                break
            yield FrameInput(
                data=data,
                ts=start_ts + frame_index / fps,
                width=width,
                height=height,
            )
            frame_index += 1
    finally:
        process.stdout.close()
        if not exhausted and process.poll() is None:
            process.terminate()
        try:
            return_code = process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            return_code = process.wait(timeout=2)
        if exhausted and return_code != 0:
            stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
            raise RuntimeError(f"FFmpeg frame stream failed: {stderr.strip()}")


def write_jpeg_crop(
    frame: FrameInput,
    box: DetectionBox,
    path: Path,
) -> tuple[float, int]:
    width = int(frame.width or 0)
    height = int(frame.height or 0)
    if not isinstance(frame.data, (bytes, bytearray)) or not width or not height:
        raise RuntimeError("Raw RGB frame data is required to save player crops")
    x = max(0, min(width - 1, round(_clamp(box.x) * width)))
    y = max(0, min(height - 1, round(_clamp(box.y) * height)))
    crop_width = max(1, min(width - x, round(_clamp(box.w) * width)))
    crop_height = max(1, min(height - y, round(_clamp(box.h) * height)))
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-i",
        "pipe:0",
        "-vf",
        f"crop={crop_width}:{crop_height}:{x}:{y}",
        "-frames:v",
        "1",
        "-q:v",
        "3",
        str(path),
    ]
    result = subprocess.run(command, input=bytes(frame.data), capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    sharpness = _sharpness(frame.data, width, x, y, crop_width, crop_height)
    return sharpness, crop_height


def run_detect_track_stage(context: ProgressContext, _: dict[str, Any]) -> None:
    from src.ml.impl.rtdetr_detector import RTDetrDetector

    settings = get_settings()
    database = Database(settings.db_path)
    job = JobRepository(database).get(context.job_id)
    project = ProjectRepository(database).get(job.project_id)
    if not project.source_id:
        raise RuntimeError("Project has no source video")
    source = SourceRepository(database).get(project.source_id)
    source_path = ArtifactService(settings).resolve_source_path(
        project.project_id, source.file_path
    )
    if str(source_path) != source.file_path:
        source.file_path = str(source_path)
        SourceRepository(database).save(source)
    DetectTrackStage(
        settings=settings,
        database=database,
        detector=RTDetrDetector(),
        tracker_factory=lambda: ByteTrackAdapter(frame_rate=settings.analysis_fps),
    ).process(
        context,
        project.project_id,
        source,
        checkpoint=job.checkpoint,
    )


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _assign_track_ids(
    boxes: Sequence[DetectionBox],
    tracked: Sequence[TrackedDetection],
) -> list[tuple[DetectionBox, int | None]]:
    unmatched = set(range(len(boxes)))
    assignments: list[tuple[DetectionBox, int | None]] = []
    for item in tracked:
        candidates = [
            (_box_iou(item.box, boxes[index]), index)
            for index in unmatched
        ]
        overlap, index = max(candidates, default=(0.0, -1))
        if index >= 0 and overlap >= 0.3:
            unmatched.remove(index)
            assignments.append((boxes[index], item.tracker_id))
        else:
            assignments.append((item.box, item.tracker_id))
    assignments.extend((boxes[index], None) for index in sorted(unmatched))
    return assignments


def _box_iou(first: DetectionBox, second: DetectionBox) -> float:
    left = max(first.x, second.x)
    top = max(first.y, second.y)
    right = min(first.x + first.w, second.x + second.w)
    bottom = min(first.y + first.h, second.y + second.h)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    union = first.w * first.h + second.w * second.h - intersection
    return intersection / union if union > 0 else 0.0


def _read_exact(stream: Any, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.read(size - len(chunks))
        if not chunk:
            break
        chunks.extend(chunk)
    return bytes(chunks)


def _sharpness(
    data: bytes | bytearray,
    frame_width: int,
    x: int,
    y: int,
    width: int,
    height: int,
) -> float:
    values: list[float] = []
    step = max(1, min(width, height) // 64)
    for row in range(y, y + height, step):
        for column in range(x, x + width, step):
            offset = (row * frame_width + column) * 3
            red, green, blue = data[offset : offset + 3]
            values.append(0.299 * red + 0.587 * green + 0.114 * blue)
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)
