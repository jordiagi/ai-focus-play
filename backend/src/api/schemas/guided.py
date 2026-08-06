from __future__ import annotations

from pydantic import BaseModel


class InferredMatchPortionResponse(BaseModel):
    start_seconds: float
    end_seconds: float
    confidence: str
    summary: str
    uncertainty_reasons: list[str] = []


class GuidedProgressResponse(BaseModel):
    stage: str
    percent: float
    message: str = ""


class ValidationErrorResponse(BaseModel):
    detail: str
