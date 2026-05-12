from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from lummevia_core import AgentRole
from lummevia_kilo import KiloExecutionMode
from lummevia_queue import TaskPriority
from lummevia_resources import ResourceType


def _capacity_id() -> str:
    return f"capacity-{uuid4()}"


def _allocation_id() -> str:
    return f"allocation-{uuid4()}"


class CapabilityBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class AllocationStatus(StrEnum):
    GRANTED = "GRANTED"
    WAITING = "WAITING"
    DENIED = "DENIED"


class AgentCapability(CapabilityBaseSchema):
    role: AgentRole
    supported_modes: list[KiloExecutionMode] = Field(default_factory=list)
    max_concurrent_tasks: int = Field(ge=1)
    supported_resource_types: list[ResourceType] = Field(default_factory=list)
    default_priority: TaskPriority = TaskPriority.NORMAL
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelCapability(CapabilityBaseSchema):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    max_concurrent_requests: int = Field(ge=1)
    estimated_cost_tier: str = Field(min_length=1)
    supports_structured_output: bool = True
    supports_long_context: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionCapacity(CapabilityBaseSchema):
    capacity_id: str = Field(default_factory=_capacity_id)
    resource_type: ResourceType
    resource_id: str = Field(min_length=1)
    max_slots: int = Field(ge=1)
    used_slots: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AllocationRequest(CapabilityBaseSchema):
    request_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    role: AgentRole
    mode: KiloExecutionMode
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    priority: TaskPriority = TaskPriority.NORMAL
    required_resources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AllocationResult(CapabilityBaseSchema):
    allocation_id: str = Field(default_factory=_allocation_id)
    status: AllocationStatus
    granted: bool = False
    reason: str | None = None
    allocated_resources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
