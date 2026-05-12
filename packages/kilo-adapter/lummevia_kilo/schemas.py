from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lummevia_core import AgentRole, TaskPackage

from lummevia_kilo.modes import KiloExecutionMode


class KiloAdapterSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class KiloExecutionStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"


class KiloRuntimeSettings(KiloAdapterSchema):
    enabled: bool = False
    dry_run: bool = True
    cli_path: Path | None = None
    workspace_root: Path | None = None
    default_timeout_seconds: int = Field(default=300, ge=1)
    allowed_repos: tuple[str, ...] = Field(default_factory=tuple)
    max_output_bytes: int = Field(default=32768, ge=1)


class KiloSafetyCheckResult(KiloAdapterSchema):
    allowed: bool
    status: str = Field(min_length=1)
    reason: str | None = None
    repo_name: str | None = None
    normalized_repo_path: str | None = None
    workspace_root: str | None = None


class KiloPreparedWorkspace(KiloAdapterSchema):
    workspace_path: Path
    source_repo_path: Path | None = None
    source_repo_readonly: bool = True


class KiloSubprocessResult(KiloAdapterSchema):
    exit_code: int
    stdout_preview: str = ""
    stderr_preview: str = ""
    stdout_bytes: int = Field(default=0, ge=0)
    stderr_bytes: int = Field(default=0, ge=0)
    duration_ms: int = Field(default=0, ge=0)
    timed_out: bool = False
    command_preview: str = Field(min_length=1)
    workspace_path: str = Field(min_length=1)


class KiloRetryPolicy(KiloAdapterSchema):
    max_attempts: int = Field(default=1, ge=1)


class KiloExecutionAttempt(KiloAdapterSchema):
    attempt_number: int = Field(ge=1)
    status: KiloExecutionStatus
    error: str | None = None


class KiloExecutionRecord(KiloAdapterSchema):
    execution_id: str = Field(min_length=1)
    session_id: str | None = None
    role: AgentRole
    mode: KiloExecutionMode
    task_id: str = Field(min_length=1)
    status: KiloExecutionStatus
    final_status: KiloExecutionStatus
    retry_count: int = Field(default=0, ge=0)
    attempts: list[KiloExecutionAttempt] = Field(default_factory=list)
    lifecycle: list[KiloExecutionStatus] = Field(default_factory=list)
    error: str | None = None


class KiloExecutionRequest(KiloAdapterSchema):
    run_id: str = Field(min_length=1)
    session_id: str | None = None
    role: AgentRole
    mode: KiloExecutionMode
    project: str = Field(min_length=1)
    repo_path: str = Field(min_length=1)
    task_package: TaskPackage
    metadata: dict[str, Any] = Field(default_factory=dict)
    retry_policy: KiloRetryPolicy = Field(default_factory=KiloRetryPolicy)


class KiloExecutionResult(KiloExecutionRecord):
    summary: str = Field(min_length=1)
    generated_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    duration_ms: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)
