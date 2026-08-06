from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from src.ml.impl.sam2_propagator import SAM2Propagator
from src.ml.interfaces import FrameInput


@pytest.mark.ml
def test_sam2_propagates_a_point_through_three_frames() -> None:
    frames = []
    for index in range(3):
        image = Image.new("RGB", (96, 64), "green")
        ImageDraw.Draw(image).rectangle(
            (38 + index, 16, 58 + index, 54),
            fill="blue",
        )
        frames.append(
            FrameInput(
                data=image,
                ts=index / 6,
                width=image.width,
                height=image.height,
            )
        )

    observations = SAM2Propagator().propagate(frames, 1, (0.5, 0.5))

    assert [item.frame_index for item in observations] == [0, 1, 2]
    assert all(item.box is not None for item in observations)
