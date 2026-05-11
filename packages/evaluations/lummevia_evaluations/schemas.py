from __future__ import annotations

from enum import StrEnum
from datetime import datetime
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


class RegressionRunSummary(EvaluationBaseSchema):
    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    avg_score: float = Field(ge=0.0, le=1.0)
    avg_latency_ms: float = Field(ge=0.0)


class RegressionCaseResult(EvaluationBaseSchema):
    case_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    input_prompt: str = Field(min_length=1)
    expected_keywords: list[str] = Field(default_factory=list)
    expected_sections: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    passed: bool = False
    score: float = Field(ge=0.0, le=1.0)
    latency_ms: int = Field(ge=0)
    fallback_used: bool = False
    evaluation_status: EvaluationStatus
    prompt_hash: str | None = Field(default=None, min_length=64, max_length=64)
    output: str | None = None
    structured_output: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegressionRunResult(EvaluationBaseSchema):
    regression_run_id: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    summary: RegressionRunSummary
    cases: list[RegressionCaseResult] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime


class PromotionStatus(StrEnum):
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class PromptBaseline(EvaluationBaseSchema):
    template_id: str = Field(min_length=1)
    active_version: str = Field(min_length=1)
    promoted_at: datetime
    promoted_by: str | None = None
    regression_summary: RegressionRunSummary
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptPromotionResult(EvaluationBaseSchema):
    template_id: str = Field(min_length=1)
    previous_version: str | None = None
    promoted_version: str = Field(min_length=1)
    promotion_status: PromotionStatus
    regression_passed: bool
    review_required: bool = False
    review_id: str | None = None
    summary: str = Field(min_length=1)
    timestamp: datetime
