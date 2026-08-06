from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any


def _known_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
    names = {item.name for item in fields(cls)}
    return {key: value for key, value in payload.items() if key in names}


@dataclass
class TargetPlayerProfile:
    target_player_profile_id: str
    team_side: str
    team_color_notes: str = ""
    jersey_number: str = ""
    appearance_notes: str = ""
    reference_frames: list[float] = field(default_factory=list)
    confirmation_status: str = "unconfirmed"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TargetPlayerProfile":
        return cls(**payload)


@dataclass
class TargetPlayerRequest:
    target_player_request_id: str
    project_id: str
    jersey_number: str
    source_id: str = ""
    optional_team_hint: str = ""
    request_status: str = "pending_evidence"
    progress_message: str = ""
    created_at: str = ""
    updated_at: str = ""
    failure_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TargetPlayerRequest":
        return cls(**_known_payload(cls, payload))


@dataclass
class EvidenceSample:
    evidence_sample_id: str
    project_id: str
    source_id: str
    candidate_id: str
    sample_type: str
    timestamp_seconds: float
    start_seconds: float
    end_seconds: float
    media_uri: str
    thumbnail_uri: str
    artifact_path: str
    origin: str = "source_video"
    jersey_number_status: str = "unknown"
    jersey_color_status: str = "unknown"
    visible_cues: list[str] = field(default_factory=list)
    cue_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvidenceSample":
        return cls(**_known_payload(cls, payload))


@dataclass
class CandidatePlayerEvidence:
    candidate_id: str
    project_id: str
    jersey_number: str
    confidence: float
    frame_time_seconds: float
    uncropped_image_uri: str
    cue_summary: str
    visible_cues: list[str] = field(default_factory=list)
    review_state: str = "candidate"
    source_id: str = ""
    target_player_request_id: str = ""
    inferred_team_color: str = ""
    evidence_count: int = 0
    sample_ids: list[str] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)
    match_reasons: list[str] = field(default_factory=list)
    review_warning: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["frame_time_seconds"] = payload["frame_time_seconds"]
        payload["uncropped_image_uri"] = payload["uncropped_image_uri"]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CandidatePlayerEvidence":
        return cls(**_known_payload(cls, payload))


@dataclass
class PlayerIdentityProfile:
    player_identity_profile_id: str
    project_id: str
    jersey_number: str
    confirmed_candidate_ids: list[str] = field(default_factory=list)
    approved_sample_ids: list[str] = field(default_factory=list)
    jersey_color: str = ""
    body_shape_summary: str = ""
    cleat_summary: str = ""
    confidence_status: str = "confirmed"
    confirmed_at: str = ""
    evidence_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PlayerIdentityProfile":
        return cls(**_known_payload(cls, payload))
