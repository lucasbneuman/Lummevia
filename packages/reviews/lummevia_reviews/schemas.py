from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReviewBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ReviewDecision(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_CHANGES = "NEEDS_CHANGES"


class ReviewStatus(StrEnum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    COMPLETED = "COMPLETED"


class ReviewType(StrEnum):
    PROMPT_PROMOTION = "PROMPT_PROMOTION"
    BUSINESS_BRIEF = "BUSINESS_BRIEF"
    TASK_PLAN = "TASK_PLAN"
    QA_VALIDATION = "QA_VALIDATION"
    QC_APPROVAL = "QC_APPROVAL"
    EXECUTION_DECISION = "EXECUTION_DECISION"
    ADAPTIVE_PLAN = "ADAPTIVE_PLAN"
    OPTIMIZATION_RECOMMENDATION = "OPTIMIZATION_RECOMMENDATION"


class HumanReview(ReviewBaseSchema):
    review_id: str = Field(min_length=1)
    review_type: ReviewType
    target_id: str = Field(min_length=1)
    target_type: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    assigned_to: str | None = None
    status: ReviewStatus
    decision: ReviewDecision | None = None
    notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
