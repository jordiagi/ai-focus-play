from __future__ import annotations

from typing import Sequence

from src.ml.device import get_device
from src.ml.interfaces import DetectionBox, FrameInput
from src.ml.model_registry import MODEL_BY_ROLE


class RTDetrDetector:
    def __init__(
        self,
        *,
        confidence_threshold: float = 0.35,
        input_size: int = 1_280,
        batch_size: int = 4,
    ) -> None:
        from transformers import AutoImageProcessor, RTDetrV2ForObjectDetection

        spec = MODEL_BY_ROLE["detector"]
        self.device = get_device()
        self.confidence_threshold = confidence_threshold
        self.input_size = input_size
        self.batch_size = max(1, batch_size)
        self.processor = AutoImageProcessor.from_pretrained(
            spec.repo_id,
            revision=spec.revision,
        )
        self.model = RTDetrV2ForObjectDetection.from_pretrained(
            spec.repo_id,
            revision=spec.revision,
        ).to(self.device)
        self.model.eval()
        labels = getattr(self.model.config, "id2label", {})
        self.person_class_ids = {
            int(class_id)
            for class_id, label in labels.items()
            if str(label).lower() == "person"
        }
        if not self.person_class_ids:
            self.person_class_ids = {1}

    def detect(self, frames: Sequence[FrameInput]) -> list[list[DetectionBox]]:
        if not frames:
            return []
        results: list[list[DetectionBox]] = []
        for offset in range(0, len(frames), self.batch_size):
            results.extend(self._detect_batch(frames[offset : offset + self.batch_size]))
        return results

    def _detect_batch(
        self, frames: Sequence[FrameInput]
    ) -> list[list[DetectionBox]]:
        import torch
        from PIL import Image

        images = []
        dimensions: list[tuple[int, int]] = []
        for frame in frames:
            width = int(frame.width or 0)
            height = int(frame.height or 0)
            if not width or not height:
                raise ValueError("RT-DETR requires frame width and height")
            if isinstance(frame.data, (bytes, bytearray)):
                image = Image.frombytes("RGB", (width, height), bytes(frame.data))
            elif isinstance(frame.data, Image.Image):
                image = frame.data.convert("RGB")
            else:
                image = Image.fromarray(frame.data).convert("RGB")
            images.append(image)
            dimensions.append((height, width))

        inputs = self.processor(
            images=images,
            return_tensors="pt",
            size={"height": self.input_size, "width": self.input_size},
        )
        inputs = {name: value.to(self.device) for name, value in inputs.items()}
        with torch.inference_mode():
            outputs = self.model(**inputs)
        processed = self.processor.post_process_object_detection(
            outputs,
            threshold=self.confidence_threshold,
            target_sizes=torch.tensor(dimensions, device=self.device),
        )
        batch_results: list[list[DetectionBox]] = []
        for result, (height, width) in zip(processed, dimensions):
            boxes: list[DetectionBox] = []
            for xyxy, score, label in zip(
                result["boxes"], result["scores"], result["labels"]
            ):
                class_id = int(label.item())
                if class_id not in self.person_class_ids:
                    continue
                x1, y1, x2, y2 = (float(value.item()) for value in xyxy)
                boxes.append(
                    DetectionBox(
                        x=max(0.0, min(1.0, x1 / width)),
                        y=max(0.0, min(1.0, y1 / height)),
                        w=max(0.0, min(1.0, (x2 - x1) / width)),
                        h=max(0.0, min(1.0, (y2 - y1) / height)),
                        confidence=float(score.item()),
                        class_id=class_id,
                    )
                )
            batch_results.append(boxes)
        return batch_results
