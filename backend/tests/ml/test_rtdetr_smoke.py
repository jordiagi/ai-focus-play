from __future__ import annotations

import pytest

from src.ml.impl.rtdetr_detector import RTDetrDetector
from src.ml.interfaces import FrameInput


@pytest.mark.ml
def test_rtdetr_detects_a_batch_of_ten_frames() -> None:
    width, height = 320, 180
    frames = [
        FrameInput(
            data=bytes([40, 110, 60]) * width * height,
            ts=index / 6,
            width=width,
            height=height,
        )
        for index in range(10)
    ]

    detections = RTDetrDetector(batch_size=2).detect(frames)

    assert len(detections) == len(frames)
    assert all(
        0 <= box.x <= 1
        and 0 <= box.y <= 1
        and 0 <= box.w <= 1
        and 0 <= box.h <= 1
        for boxes in detections
        for box in boxes
    )
