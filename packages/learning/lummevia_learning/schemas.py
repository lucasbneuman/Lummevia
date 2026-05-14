from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _signal_id() -> str:
    return f"signal-{uuid4()}"


def _insight_id() -> str:
    return f"insight-{uuid4()}"


def _recommendation_id() -> str:
    return f"recommendation-{uuid4()}"


class LearningBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class SignalType(StrEnum):
    QA_FAILURES_REPEATED = "QA_FAILURES_REPEATED"
    HIGH_RETRY_RATE = "HIGH_RETRY_RATE"
    HIGH_COST = "HIGH_COST"
    HIGH_LATENCY = "HIGH_LATENCY"
    MANY_NEEDS_REVIEW = "MANY_NEEDS_REVIEW"
    DEAD_LETTERS = "DEAD_LETTERS"
    LOW_PROMPT_SCORE = "LOW_PROMPT_SCORE"
    FREQUENT_RECOVERY_STRATEGY = "FREQUENT_RECOVERY_STRATEGY"


class InsightType(StrEnum):
    QUALITY = "QUALITY"
    EXECUTION_INSTABILITY = "EXECUTION_INSTABILITY"
    ECONOMIC = "ECONOMIC"
    PERFORMANCE = "PERFORMANCE"
    GOVERNANCE = "GOVERNANCE"
    RESILIENCE = "RESILIENCE"
    PROMPT_QUALITY = "PROMPT_QUALITY"
    PLANNING_WEAKNESS = "PLANNING_WEAKNESS"


class RecommendationType(StrEnum):
    IMPROVE_PROMPT = "IMPROVE_PROMPT"
    SPLIT_TASK_PACKAGE = "SPLIT_TASK_PACKAGE"
    STRICTER_QA = "STRICTER_QA"
    LOWER_AUTONOMY = "LOWER_AUTONOMY"
    USE_MODEL_LITE = "USE_MODEL_LITE"
    ADD_MEMORY_CONTEXT = "ADD_MEMORY_CONTEXT"
    REVIEW_STRATEGY = "REVIEW_STRATEGY"
    CREATE_REVIEW_GATE = "CREATE_REVIEW_GATE"


class LearningSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecommendationStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class LearningSignal(LearningBaseSchema):
    signal_id: str = Field(default_factory=_signal_id)
    project: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    signal_type: SignalType
    severity: LearningSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperationalInsight(LearningBaseSchema):
    insight_id: str = Field(default_factory=_insight_id)
    project: str = Field(min_length=1)
    insight_type: InsightType
    severity: LearningSeverity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class OptimizationRecommendation(LearningBaseSchema):
    recommendation_id: str = Field(default_factory=_recommendation_id)
    project: str = Field(min_length=1)
    recommendation_type: RecommendationType
    status: RecommendationStatus = RecommendationStatus.PROPOSED
    confidence: float = Field(ge=0.0, le=1.0)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    expected_impact: str = Field(min_length=1)
    requires_human_review: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
