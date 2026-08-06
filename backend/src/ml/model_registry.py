from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    role: str
    repo_id: str
    revision: str
    size_mb: int
    source: str = "huggingface"


MODELS = (
    ModelSpec(
        "detector",
        "PekingU/rtdetr_v2_r50vd",
        "282494075698cab9faa1096ae26856890030c817",
        172,
    ),
    ModelSpec(
        "embedder",
        "facebook/dinov2-small",
        "169e7c34622d7a7c466d7d9aabcec09c35c9a91e",
        90,
    ),
    ModelSpec(
        "jersey_ocr",
        "baudm/parseq",
        "1902db043c029a7e03a3818c616c06600af574be",
        90,
        source="torch_hub",
    ),
    ModelSpec(
        "click_refinement",
        "facebook/sam2.1-hiera-small",
        "6c381d9c16faed5e8a7c4a2cd99918bdca8316e4",
        185,
    ),
)

MODEL_BY_ROLE = {model.role: model for model in MODELS}
