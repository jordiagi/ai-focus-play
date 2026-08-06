from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ReviewDecision:
    review_decision_id: str
    detection_id: str
    decision: str
    reviewed_at: str
    reviewer_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ReviewDecision":
        return cls(**payload)

