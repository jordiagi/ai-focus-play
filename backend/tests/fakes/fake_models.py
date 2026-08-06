from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Sequence

from src.ml.interfaces import (
    CropInput,
    DetectionBox,
    FrameInput,
    MaskObservation,
    TextReading,
)


class FakeDetector:
    def __init__(self, ground_truth_path: Path) -> None:
        payload = json.loads(ground_truth_path.read_text())
        self.frames = payload["frames"]

    def detect(self, frames: Sequence[FrameInput]) -> list[list[DetectionBox]]:
        results: list[list[DetectionBox]] = []
        for frame in frames:
            truth = min(self.frames, key=lambda item: abs(item["ts"] - frame.ts))
            results.append(
                [
                    DetectionBox(
                        x=item["x"],
                        y=item["y"],
                        w=item["w"],
                        h=item["h"],
                        confidence=item.get("confidence", 0.99),
                        identity_id=item.get("identity_id"),
                    )
                    for item in truth["detections"]
                ]
            )
        return results


class FakeEmbedder:
    def embed(self, crops: Sequence[CropInput]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for crop in crops:
            key = crop.identity_id or "unknown"
            raw = hashlib.sha256(key.encode()).digest()[:16]
            vector = [(value - 127.5) / 127.5 for value in raw]
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


class FakeOCR:
    def recognize(self, crops: Sequence[CropInput]) -> list[TextReading]:
        return [
            TextReading(crop.number or "", 0.99 if crop.number else 0.0)
            for crop in crops
        ]


class FakeMaskPropagator:
    def __init__(self, boxes: list[tuple[float, float, float, float] | None] | None = None) -> None:
        self.boxes = boxes

    def propagate(
        self,
        frames: Sequence[FrameInput],
        seed_index: int,
        point_norm: tuple[float, float],
    ) -> list[MaskObservation]:
        del seed_index
        default = (point_norm[0] - 0.04, point_norm[1] - 0.1, 0.08, 0.2)
        boxes = self.boxes or [default for _ in frames]
        return [
            MaskObservation(index, box, 0.99 if box else 0.0)
            for index, box in enumerate(boxes[: len(frames)])
        ]
