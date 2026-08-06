from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Sequence

from src.ml.device import get_device
from src.ml.interfaces import CropInput, TextReading
from src.ml.model_registry import MODEL_BY_ROLE


class PARSeqRecognizer:
    def __init__(self, *, batch_size: int = 32) -> None:
        import torch

        from src.ml.download_models import _download_torch_hub_repo

        spec = MODEL_BY_ROLE["jersey_ocr"]
        repository = _download_torch_hub_repo(spec.repo_id, spec.revision)
        self.device = get_device()
        self.batch_size = max(1, batch_size)
        self.model = torch.hub.load(
            str(repository),
            "parseq",
            pretrained=True,
            source="local",
            trust_repo=True,
        ).to(self.device)
        self.model.eval()
        from torchvision import transforms

        self.transform = transforms.Compose(
            [
                transforms.Resize(
                    tuple(self.model.hparams.img_size),
                    transforms.InterpolationMode.BICUBIC,
                ),
                transforms.ToTensor(),
                transforms.Normalize(0.5, 0.5),
            ]
        )

    def recognize(self, crops: Sequence[CropInput]) -> list[TextReading]:
        if not crops:
            return []
        readings: list[TextReading] = []
        for offset in range(0, len(crops), self.batch_size):
            readings.extend(
                self._recognize_batch(crops[offset : offset + self.batch_size])
            )
        return readings

    def _recognize_batch(
        self, crops: Sequence[CropInput]
    ) -> list[TextReading]:
        import torch

        batch = torch.stack(
            [self.transform(_to_image(crop.data)) for crop in crops]
        ).to(self.device)
        with torch.inference_mode():
            probabilities = self.model(batch).softmax(-1)
        labels, confidences = self.model.tokenizer.decode(probabilities)
        readings = []
        for label, confidence in zip(labels, confidences):
            digits = "".join(character for character in str(label) if character.isdigit())
            score = float(confidence.mean().item()) if len(confidence) else 0.0
            readings.append(TextReading(digits, score if digits else 0.0))
        return readings


def _to_image(data: Any):
    from PIL import Image

    if isinstance(data, Image.Image):
        return data.convert("RGB")
    if isinstance(data, (str, Path)):
        with Image.open(data) as image:
            return image.convert("RGB")
    if isinstance(data, (bytes, bytearray)):
        with Image.open(BytesIO(bytes(data))) as image:
            return image.convert("RGB")
    try:
        return Image.fromarray(data).convert("RGB")
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("PARSeq requires an image, image path, or encoded image bytes") from exc
