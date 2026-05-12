from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _memory_id() -> str:
    return f"memory-{uuid4()}"


class MemoryBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class MemoryCategory(StrEnum):
    BUSINESS_DECISION = "BUSINESS_DECISION"
    TASK_LEARNING = "TASK_LEARNING"
    QA_ISSUE = "QA_ISSUE"
    IMPLEMENTATION_NOTE = "IMPLEMENTATION_NOTE"
    PROMPT_LEARNING = "PROMPT_LEARNING"
    REVIEW_DECISION = "REVIEW_DECISION"


class MemorySourceType(StrEnum):
    CONVERSATION = "CONVERSATION"
    SESSION = "SESSION"
    REVIEW = "REVIEW"
    WORKFLOW = "WORKFLOW"
    SYSTEM = "SYSTEM"


class ProjectMemoryRecord(MemoryBaseSchema):
    memory_id: str = Field(default_factory=_memory_id)
    project: str = Field(min_length=1)
    category: MemoryCategory
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source_type: MemorySourceType
    source_id: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
