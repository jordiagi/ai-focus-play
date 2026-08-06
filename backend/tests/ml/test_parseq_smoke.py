from __future__ import annotations

import pytest

from src.ml.impl.parseq_ocr import PARSeqRecognizer
from src.ml.interfaces import CropInput


@pytest.mark.ml
def test_parseq_returns_digits_only_for_a_small_batch() -> None:
    from PIL import Image, ImageDraw

    crops = []
    for number in ("8", "11"):
        image = Image.new("RGB", (160, 96), "white")
        ImageDraw.Draw(image).text((45, 20), number, fill="black", font_size=48)
        crops.append(CropInput(data=image))

    readings = PARSeqRecognizer(batch_size=2).recognize(crops)

    assert len(readings) == 2
    assert all(not reading.text or reading.text.isdigit() for reading in readings)
    assert all(0 <= reading.confidence <= 1 for reading in readings)
