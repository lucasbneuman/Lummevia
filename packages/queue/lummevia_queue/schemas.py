from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from lummevia_core import AgentRole
from lummevia_kilo import KiloExecutionMode


def _queue_id() -> str:
    return f"queue-{uuid4()}"


def _queue_item_id() -> str:
    return f"queue-item-{uuid4()}"


class QueueBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class TaskQueueStatus(StrEnum):
    QUEUED = "QUEUED"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskQueueItem(QueueBaseSchema):
    queue_item_id: str = Field(default_factory=_queue_item_id)
    task_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskQueueStatus = TaskQueueStatus.QUEUED
    dependencies: list[str] = Field(default_factory=list)
    assigned_role: AgentRole
    mode: KiloExecutionMode
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskQueue(QueueBaseSchema):
    queue_id: str = Field(default_factory=_queue_id)
    project: str = Field(min_length=1)
    workflow_run_id: str = Field(min_length=1)
    items: list[TaskQueueItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
