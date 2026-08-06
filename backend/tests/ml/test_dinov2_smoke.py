from __future__ import annotations

import math

import pytest

from src.ml.impl.dinov2_embedder import DINOv2Embedder
from src.ml.interfaces import CropInput


@pytest.mark.ml
def test_dinov2_embeds_four_crops_as_normalized_vectors() -> None:
    from PIL import Image

    crops = [
        CropInput(data=Image.new("RGB", (96, 160), color))
        for color in ("red", "blue", "green", "white")
    ]

    vectors = DINOv2Embedder(batch_size=2).embed(crops)

    assert len(vectors) == 4
    assert all(len(vector) == 384 for vector in vectors)
    assert all(
        math.isclose(
            math.sqrt(sum(value * value for value in vector)),
            1.0,
            rel_tol=1e-5,
        )
        for vector in vectors
    )
