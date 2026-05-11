from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluationBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class EvaluationStatus(StrEnum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class PromptEvaluation(EvaluationBaseSchema):
    evaluation_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    status: EvaluationStatus
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
