from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from lummevia_core import AgentRole, TaskPackage

from lummevia_kilo.modes import KiloExecutionMode


class KiloAdapterSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class KiloExecutionRequest(KiloAdapterSchema):
    run_id: str = Field(min_length=1)
    role: AgentRole
    mode: KiloExecutionMode
    project: str = Field(min_length=1)
    repo_path: str = Field(min_length=1)
    task_package: TaskPackage
    metadata: dict[str, Any] = Field(default_factory=dict)


class KiloExecutionResult(KiloAdapterSchema):
    execution_id: str = Field(min_length=1)
    status: Literal["completed", "failed", "skipped"]
    summary: str = Field(min_length=1)
    generated_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    duration_ms: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
