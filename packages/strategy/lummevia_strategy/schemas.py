from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _strategy_id() -> str:
    return f"strategy-{uuid4()}"


class StrategyBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class StrategyType(StrEnum):
    SAFE = "SAFE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"
    RECOVERY = "RECOVERY"
    VALIDATION_HEAVY = "VALIDATION_HEAVY"
    COST_OPTIMIZED = "COST_OPTIMIZED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SandboxLevel(StrEnum):
    NONE = "NONE"
    BASIC = "BASIC"
    ISOLATED = "ISOLATED"
    STRICT = "STRICT"


class QALevel(StrEnum):
    BASIC = "BASIC"
    STANDARD = "STANDARD"
    STRICT = "STRICT"
    PARANOID = "PARANOID"


class AutonomyLevel(StrEnum):
    MANUAL = "MANUAL"
    ASSISTED = "ASSISTED"
    SUPERVISED = "SUPERVISED"
    AUTONOMOUS = "AUTONOMOUS"


class ExecutionStrategy(StrategyBaseSchema):
    strategy_id: str = Field(default_factory=_strategy_id)
    workflow_run_id: str = Field(min_length=1)
    session_id: str | None = None
    strategy_type: StrategyType
    autonomy_level: AutonomyLevel
    selected_model: str = Field(min_length=1)
    selected_provider: str = Field(min_length=1)
    execution_mode: str = Field(min_length=1)
    qa_level: QALevel
    sandbox_level: SandboxLevel
    retry_policy: str = Field(min_length=1)
    risk_level: RiskLevel
    reasoning: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionStrategyContext(StrategyBaseSchema):
    workflow_run_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    step_name: str = Field(min_length=1)
    session_id: str | None = None
    task_id: str | None = None
    workflow_state: str | None = None
    execution_layer: str = "WORKFLOW"
    execution_mode: str | None = None
    files_changed_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    qa_fail_count: int = Field(default=0, ge=0)
    prior_failure_count: int = Field(default=0, ge=0)
    prior_qa_issue_count: int = Field(default=0, ge=0)
    prior_review_count: int = Field(default=0, ge=0)
    prior_dead_letter_count: int = Field(default=0, ge=0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    project_is_new: bool = False
    history_is_stable: bool = False
    sandbox_real: bool = False
    cost_pressure_high: bool = False
    dead_letter_risk: bool = False
    previous_strategy_type: StrategyType | None = None
    previous_risk_level: RiskLevel | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
