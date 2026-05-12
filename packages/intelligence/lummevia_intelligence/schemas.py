from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _decision_id() -> str:
    return f"decision-{uuid4()}"


class IntelligenceBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class DecisionType(StrEnum):
    CONTINUE = "CONTINUE"
    RETRY = "RETRY"
    ESCALATE_REVIEW = "ESCALATE_REVIEW"
    SPLIT_TASK = "SPLIT_TASK"
    STOP = "STOP"
    REQUEUE = "REQUEUE"
    DISCARD_CHANGES = "DISCARD_CHANGES"
    REQUEST_MORE_CONTEXT = "REQUEST_MORE_CONTEXT"


class DecisionStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"


class AutonomyLevel(StrEnum):
    MANUAL = "MANUAL"
    ASSISTED = "ASSISTED"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"


class ExecutionDecision(IntelligenceBaseSchema):
    decision_id: str = Field(default_factory=_decision_id)
    workflow_run_id: str = Field(min_length=1)
    session_id: str | None = None
    task_id: str | None = None
    decision_type: DecisionType
    status: DecisionStatus = DecisionStatus.PROPOSED
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)
    requires_human_review: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionContext(IntelligenceBaseSchema):
    workflow_run_id: str = Field(min_length=1)
    session_id: str | None = None
    task_id: str | None = None
    autonomy_level: AutonomyLevel = AutonomyLevel.MANUAL
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=1, ge=1)
    files_changed_count: int = Field(default=0, ge=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    validation_status: str | None = None
    qa_status: str | None = None
    missing_context: bool = False
    task_too_large: bool = False
    kilo_failed: bool = False
    stuck_detected: bool = False
    dead_lettered: bool = False
    real_code_touched: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
