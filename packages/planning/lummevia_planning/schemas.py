from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _adaptive_plan_id() -> str:
    return f"adaptive-plan-{uuid4()}"


def _mutation_id() -> str:
    return f"plan-mutation-{uuid4()}"


class PlanningBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class MutationType(StrEnum):
    SPLIT_TASK = "SPLIT_TASK"
    REQUEUE_TASK = "REQUEUE_TASK"
    INSERT_REVIEW = "INSERT_REVIEW"
    INSERT_QA = "INSERT_QA"
    REPLAN_DEPENDENCIES = "REPLAN_DEPENDENCIES"
    ESCALATE_TASK = "ESCALATE_TASK"
    REGENERATE_PROMPT = "REGENERATE_PROMPT"


class AdaptivePlanStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"


class PlanMutation(PlanningBaseSchema):
    mutation_id: str = Field(default_factory=_mutation_id)
    adaptive_plan_id: str = Field(min_length=1)
    mutation_type: MutationType
    target: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProposedTaskPackage(PlanningBaseSchema):
    task_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    dependencies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueueRecommendation(PlanningBaseSchema):
    action: str = Field(min_length=1)
    target: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AdaptivePlan(PlanningBaseSchema):
    adaptive_plan_id: str = Field(default_factory=_adaptive_plan_id)
    workflow_run_id: str = Field(min_length=1)
    source_task_id: str | None = None
    trigger_reason: str = Field(min_length=1)
    status: AdaptivePlanStatus = AdaptivePlanStatus.PROPOSED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
    mutations: list[PlanMutation] = Field(default_factory=list)
    proposed_task_packages: list[ProposedTaskPackage] = Field(default_factory=list)
    queue_recommendations: list[QueueRecommendation] = Field(default_factory=list)


class AdaptivePlanningContext(PlanningBaseSchema):
    workflow_run_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    source_task_id: str | None = None
    trigger_reason: str = Field(min_length=1)
    files_changed_count: int = Field(default=0, ge=0)
    qa_fail_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=1, ge=1)
    missing_context: bool = False
    dependency_blocked: bool = False
    validation_inconsistent: bool = False
    failed_validation: bool = False
    dead_letter_risk: bool = False
    task_package_size: int = Field(default=0, ge=0)
    blocked_dependencies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
