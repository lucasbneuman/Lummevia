from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _event_id() -> str:
    return f"supervisor-event-{uuid4()}"


def _action_id() -> str:
    return f"recovery-action-{uuid4()}"


def _dead_letter_id() -> str:
    return f"dead-letter-{uuid4()}"


def _watchdog_id() -> str:
    return f"watchdog-{uuid4()}"


class SupervisorBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ExecutionHealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    WAITING = "WAITING"
    RUNNING = "RUNNING"
    STUCK = "STUCK"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RECOVERING = "RECOVERING"
    DEAD_LETTER = "DEAD_LETTER"


class RecoveryActionType(StrEnum):
    RETRY = "RETRY"
    CANCEL = "CANCEL"
    RELEASE_LOCKS = "RELEASE_LOCKS"
    REQUEUE = "REQUEUE"
    MARK_DEAD_LETTER = "MARK_DEAD_LETTER"
    RESUME = "RESUME"


class RecoveryActionStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class WatchdogStatus(StrEnum):
    ACTIVE = "ACTIVE"
    STUCK = "STUCK"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SupervisorEvent(SupervisorBaseSchema):
    event_id: str = Field(default_factory=_event_id)
    workflow_run_id: str = Field(min_length=1)
    session_id: str | None = None
    queue_item_id: str | None = None
    event_type: str = Field(min_length=1)
    status: ExecutionHealthStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecoveryAction(SupervisorBaseSchema):
    action_id: str = Field(default_factory=_action_id)
    workflow_run_id: str = Field(min_length=1)
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    action_type: RecoveryActionType
    status: RecoveryActionStatus = RecoveryActionStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeadLetterItem(SupervisorBaseSchema):
    dead_letter_id: str = Field(default_factory=_dead_letter_id)
    workflow_run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    queue_item_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionWatchdog(SupervisorBaseSchema):
    watchdog_id: str = Field(default_factory=_watchdog_id)
    workflow_run_id: str = Field(min_length=1)
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    timeout_seconds: int = Field(ge=1)
    status: WatchdogStatus = WatchdogStatus.ACTIVE
    last_heartbeat_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
