from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Detection:
    source_id: str
    ts: float
    x: float
    y: float
    w: float
    h: float
    conf: float | None = None
    tracklet_id: str | None = None
    detection_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Tracklet:
    tracklet_id: str
    source_id: str
    start_ts: float
    end_ts: float
    frame_count: int
    avg_conf: float | None = None
    kit_color_name: str | None = None
    kit_color_hsv: str | None = None
    cluster_id: str | None = None
    cluster_assignment: str | None = "auto"
    synthetic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrackletCrop:
    crop_id: str
    tracklet_id: str
    ts: float
    crop_path: str
    sharpness: float | None = None
    bbox_h_px: int | None = None
    purpose: str = "sample"


@dataclass
class TrackletEmbedding:
    tracklet_id: str
    model: str
    dim: int
    vector: bytes
    crop_count: int


@dataclass
class IdentityCluster:
    cluster_id: str
    source_id: str
    tracklet_count: int
    screen_time_s: float
    status: str = "candidate"
    jersey_number: str | None = None
    jersey_conf: float | None = None
    kit_color_name: str | None = None
    rep_crop_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JerseyVote:
    vote_id: str
    tracklet_id: str
    ts: float
    text: str
    conf: float
    model: str
    crop_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
