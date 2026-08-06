from __future__ import annotations

import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any, Sequence

from src.ml.device import get_device
from src.ml.interfaces import FrameInput, MaskObservation
from src.ml.model_registry import MODEL_BY_ROLE


class SAM2Propagator:
    def __init__(self) -> None:
        from sam2.build_sam import build_sam2_video_predictor

        spec = MODEL_BY_ROLE["click_refinement"]
        self.device = get_device()
        checkpoint = _checkpoint_path(spec.repo_id, spec.revision)
        self.predictor = build_sam2_video_predictor(
            "configs/sam2.1/sam2.1_hiera_s.yaml",
            ckpt_path=str(checkpoint),
            device=self.device,
        )

    def propagate(
        self,
        frames: Sequence[FrameInput],
        seed_index: int,
        point_norm: tuple[float, float],
    ) -> list[MaskObservation]:
        import numpy as np

        if not frames:
            return []
        if not 0 <= seed_index < len(frames):
            raise ValueError("SAM 2 seed frame is outside the refinement window")
        with tempfile.TemporaryDirectory(prefix="ai-focus-sam2-") as temporary:
            video_dir = Path(temporary)
            images = [_to_image(frame.data) for frame in frames]
            for index, image in enumerate(images):
                image.save(video_dir / f"{index:05d}.jpg", quality=95)
            width, height = images[seed_index].size
            x = max(0.0, min(1.0, point_norm[0])) * width
            y = max(0.0, min(1.0, point_norm[1])) * height
            state = self.predictor.init_state(
                video_path=str(video_dir),
                offload_video_to_cpu=True,
                offload_state_to_cpu=True,
            )
            self.predictor.add_new_points_or_box(
                state,
                frame_idx=seed_index,
                obj_id=1,
                points=np.asarray([[x, y]], dtype=np.float32),
                labels=np.asarray([1], dtype=np.int32),
            )

            outputs = {}
            for frame_index, _, logits in self.predictor.propagate_in_video(
                state,
                start_frame_idx=seed_index,
                max_frame_num_to_track=len(frames) - seed_index,
            ):
                outputs[int(frame_index)] = logits[0] > 0
            if seed_index:
                for frame_index, _, logits in self.predictor.propagate_in_video(
                    state,
                    start_frame_idx=seed_index,
                    max_frame_num_to_track=seed_index + 1,
                    reverse=True,
                ):
                    outputs[int(frame_index)] = logits[0] > 0

        observations = []
        for frame_index in range(len(frames)):
            logits = outputs.get(frame_index)
            if logits is None:
                observations.append(MaskObservation(frame_index, None, 0.0))
                continue
            frame_width, frame_height = images[frame_index].size
            mask = logits
            while mask.ndim > 2:
                mask = mask[0]
            mask = mask.detach().cpu().bool()
            box = _mask_box(mask, frame_width, frame_height)
            observations.append(
                MaskObservation(
                    frame_index=frame_index,
                    box=box,
                    score=1.0 if box else 0.0,
                    mask=mask,
                )
            )
        return observations


def _checkpoint_path(repo_id: str, revision: str) -> Path:
    hf_home = Path(
        os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface")
    )
    snapshot = (
        hf_home
        / "hub"
        / f"models--{repo_id.replace('/', '--')}"
        / "snapshots"
        / revision
    )
    checkpoint = snapshot / "sam2.1_hiera_small.pt"
    if not checkpoint.is_file():
        raise RuntimeError(
            "SAM 2 weights are missing; run python -m src.ml.download_models"
        )
    return checkpoint


def _mask_box(
    mask: Any,
    width: int,
    height: int,
) -> tuple[float, float, float, float] | None:
    import torch

    points = torch.nonzero(mask, as_tuple=False)
    if not points.numel():
        return None
    y_min, x_min = points.min(dim=0).values.tolist()
    y_max, x_max = points.max(dim=0).values.tolist()
    return (
        float(x_min) / width,
        float(y_min) / height,
        float(x_max - x_min + 1) / width,
        float(y_max - y_min + 1) / height,
    )


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
        raise ValueError(
            "SAM 2 requires an image, image path, or encoded image bytes"
        ) from exc
