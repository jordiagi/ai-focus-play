from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class FrameInput:
    data: Any
    ts: float
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class CropInput:
    data: Any
    identity_id: str | None = None
    number: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DetectionBox:
    x: float
    y: float
    w: float
    h: float
    confidence: float
    class_id: int = 0
    identity_id: str | None = None


@dataclass(frozen=True)
class TextReading:
    text: str
    confidence: float


@dataclass(frozen=True)
class MaskObservation:
    frame_index: int
    box: tuple[float, float, float, float] | None
    score: float
    mask: Any = None


@runtime_checkable
class Detector(Protocol):
    def detect(self, frames: Sequence[FrameInput]) -> list[list[DetectionBox]]: ...


@runtime_checkable
class Embedder(Protocol):
    def embed(self, crops: Sequence[CropInput]) -> list[list[float]]: ...


@runtime_checkable
class TextRecognizer(Protocol):
    def recognize(self, crops: Sequence[CropInput]) -> list[TextReading]: ...


@runtime_checkable
class MaskPropagator(Protocol):
    def propagate(
        self,
        frames: Sequence[FrameInput],
        seed_index: int,
        point_norm: tuple[float, float],
    ) -> list[MaskObservation]: ...
