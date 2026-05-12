from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _lock_id() -> str:
    return f"lock-{uuid4()}"


class ResourceBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ResourceType(StrEnum):
    REPO = "REPO"
    WORKSPACE = "WORKSPACE"
    PATH = "PATH"
    MODEL = "MODEL"
    KILO_WORKER = "KILO_WORKER"


class ResourceLockStatus(StrEnum):
    ACQUIRED = "ACQUIRED"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class WorkspaceStatus(StrEnum):
    ALLOCATED = "ALLOCATED"
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    FAILED = "FAILED"


class ResourceLock(ResourceBaseSchema):
    lock_id: str = Field(default_factory=_lock_id)
    resource_type: ResourceType
    resource_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    owner_type: str = Field(min_length=1)
    status: ResourceLockStatus = ResourceLockStatus.ACQUIRED
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    released_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceAllocation(ResourceBaseSchema):
    workspace_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    queue_item_id: str = Field(min_length=1)
    branch_name: str = Field(min_length=1)
    worktree_path: str = Field(min_length=1)
    status: WorkspaceStatus = WorkspaceStatus.ALLOCATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    released_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
