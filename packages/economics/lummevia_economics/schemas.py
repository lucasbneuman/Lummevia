from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _budget_id() -> str:
    return f"budget-{uuid4()}"


def _usage_id() -> str:
    return f"usage-{uuid4()}"


def _decision_id() -> str:
    return f"cost-decision-{uuid4()}"


class EconomicsBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class BudgetStatus(StrEnum):
    ACTIVE = "ACTIVE"
    WARNING = "WARNING"
    EXCEEDED = "EXCEEDED"
    CLOSED = "CLOSED"


class CostControlStatus(StrEnum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    DEGRADE = "DEGRADE"
    BLOCK = "BLOCK"


class ExecutionBudget(EconomicsBaseSchema):
    budget_id: str = Field(default_factory=_budget_id)
    project: str = Field(min_length=1)
    workflow_run_id: str | None = None
    max_estimated_cost: float = Field(ge=0.0)
    max_model_calls: int = Field(ge=0)
    max_tokens_estimated: int = Field(ge=0)
    status: BudgetStatus = BudgetStatus.ACTIVE
    used_estimated_cost: float = Field(default=0.0, ge=0.0)
    used_model_calls: int = Field(default=0, ge=0)
    used_tokens_estimated: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageEstimate(EconomicsBaseSchema):
    usage_id: str = Field(default_factory=_usage_id)
    project: str = Field(min_length=1)
    workflow_run_id: str | None = None
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    role: str = Field(min_length=1)
    operation_type: str = Field(min_length=1)
    estimated_input_tokens: int = Field(ge=0)
    estimated_output_tokens: int = Field(ge=0)
    estimated_cost: float = Field(ge=0.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class CostControlDecision(EconomicsBaseSchema):
    decision_id: str = Field(default_factory=_decision_id)
    project: str = Field(min_length=1)
    workflow_run_id: str | None = None
    status: CostControlStatus
    reason: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)
    budget_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
