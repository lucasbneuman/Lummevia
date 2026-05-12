from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _timeline_id() -> str:
    return f"timeline-{uuid4()}"


class TimelineBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class TimelineSourceType(StrEnum):
    WORKFLOW = "WORKFLOW"
    CONVERSATION = "CONVERSATION"
    SESSION = "SESSION"
    REVIEW = "REVIEW"
    MEMORY = "MEMORY"
    SYSTEM = "SYSTEM"


class TimelineEvent(TimelineBaseSchema):
    event_id: str = Field(min_length=1)
    workflow_run_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    source_type: TimelineSourceType
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowTimeline(TimelineBaseSchema):
    timeline_id: str = Field(default_factory=_timeline_id)
    workflow_run_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    events: list[TimelineEvent] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
