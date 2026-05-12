from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lummevia_core import AgentRole
from lummevia_kilo import KiloExecutionMode


class SessionBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class SessionStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_REVIEW = "WAITING_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class SessionEvent(SessionBaseSchema):
    event_id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    message: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionOutput(SessionBaseSchema):
    output_id: str = Field(min_length=1)
    output_type: str = Field(min_length=1)
    content: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskExecutionSession(SessionBaseSchema):
    session_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    queue_id: str | None = None
    queue_item_id: str | None = None
    workspace_id: str | None = None
    branch_name: str | None = None
    worktree_path: str | None = None
    lock_ids: list[str] = Field(default_factory=list)
    role: AgentRole
    mode: KiloExecutionMode
    status: SessionStatus
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    attempts: int = Field(default=0, ge=0)
    health_status: str = "WAITING"
    watchdog_id: str | None = None
    retry_attempts: int = Field(default=0, ge=0)
    recovery_history: list[str] = Field(default_factory=list)
    events: list[SessionEvent] = Field(default_factory=list)
    outputs: list[SessionOutput] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
