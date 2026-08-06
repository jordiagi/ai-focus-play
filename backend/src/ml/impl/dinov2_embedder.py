from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Sequence

from src.ml.device import get_device
from src.ml.interfaces import CropInput
from src.ml.model_registry import MODEL_BY_ROLE


class DINOv2Embedder:
    def __init__(self, *, batch_size: int = 64) -> None:
        from transformers import AutoImageProcessor, AutoModel

        spec = MODEL_BY_ROLE["embedder"]
        self.device = get_device()
        self.batch_size = max(1, batch_size)
        self.processor = AutoImageProcessor.from_pretrained(
            spec.repo_id,
            revision=spec.revision,
        )
        self.model = AutoModel.from_pretrained(
            spec.repo_id,
            revision=spec.revision,
        ).to(self.device)
        self.model.eval()

    def embed(self, crops: Sequence[CropInput]) -> list[list[float]]:
        if not crops:
            return []
        vectors: list[list[float]] = []
        for offset in range(0, len(crops), self.batch_size):
            vectors.extend(self._embed_batch(crops[offset : offset + self.batch_size]))
        return vectors

    def _embed_batch(self, crops: Sequence[CropInput]) -> list[list[float]]:
        import torch

        images = [_to_image(crop.data) for crop in crops]
        inputs = self.processor(images=images, return_tensors="pt")
        inputs = {name: value.to(self.device) for name, value in inputs.items()}
        with torch.inference_mode():
            hidden = self.model(**inputs).last_hidden_state
            patch_tokens = hidden[:, 1:] if hidden.shape[1] > 1 else hidden
            pooled = patch_tokens.mean(dim=1)
            normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
        return normalized.detach().cpu().float().tolist()


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
        raise ValueError("DINOv2 requires an image, image path, or encoded image bytes") from exc
