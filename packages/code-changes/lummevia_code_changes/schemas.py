from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _change_set_id() -> str:
    return f"change-set-{uuid4()}"


def _artifact_id() -> str:
    return f"code-artifact-{uuid4()}"


class CodeChangeBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class CodeChangeStatus(StrEnum):
    DETECTED = "DETECTED"
    VALIDATED = "VALIDATED"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    REVERTED = "REVERTED"
    DISCARDED = "DISCARDED"


class ChangedFile(CodeChangeBaseSchema):
    path: str = Field(min_length=1)
    change_type: str = Field(min_length=1)
    lines_added: int = Field(default=0, ge=0)
    lines_removed: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodeArtifact(CodeChangeBaseSchema):
    artifact_id: str = Field(default_factory=_artifact_id, min_length=1)
    artifact_type: str = Field(min_length=1)
    path: str = Field(min_length=1)
    checksum: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodeChangeSet(CodeChangeBaseSchema):
    change_set_id: str = Field(default_factory=_change_set_id, min_length=1)
    execution_id: str = Field(min_length=1)
    session_id: str | None = None
    task_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    repo: str = Field(min_length=1)
    workspace_id: str | None = None
    status: CodeChangeStatus = CodeChangeStatus.DETECTED
    files_changed: list[ChangedFile] = Field(default_factory=list)
    diff_summary: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[CodeArtifact] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileSnapshot(CodeChangeBaseSchema):
    path: str = Field(min_length=1)
    checksum: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    line_count: int = Field(ge=0)
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceSnapshot(CodeChangeBaseSchema):
    root_path: str = Field(min_length=1)
    files: dict[str, FileSnapshot] = Field(default_factory=dict)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkspaceDiffResult(CodeChangeBaseSchema):
    files_changed: list[ChangedFile] = Field(default_factory=list)
    diff_summary: dict[str, Any] = Field(default_factory=dict)
    lines_added: int = Field(default=0, ge=0)
    lines_removed: int = Field(default=0, ge=0)


def checksum_for_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def checksum_for_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def normalize_artifact_path(path: str | Path) -> str:
    return str(Path(path))
