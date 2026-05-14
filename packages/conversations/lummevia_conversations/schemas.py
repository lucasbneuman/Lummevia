from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _thread_id() -> str:
    return f"thread-{uuid4()}"


def _message_id() -> str:
    return f"message-{uuid4()}"


class ConversationBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ConversationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    APPROVED = "APPROVED"
    CLOSED = "CLOSED"


class ConversationPhase(StrEnum):
    STARTED = "STARTED"
    DISCOVERY = "DISCOVERY"
    PM_QUESTIONS = "PM_QUESTIONS"
    DRAFTING_BRIEF = "DRAFTING_BRIEF"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    CLOSED = "CLOSED"


class AuthorType(StrEnum):
    FOUNDER = "FOUNDER"
    PM = "PM"
    SYSTEM = "SYSTEM"


class ConversationMessage(ConversationBaseSchema):
    message_id: str = Field(default_factory=_message_id)
    role: str = Field(min_length=1)
    author_type: AuthorType
    content: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class FounderPMConversationState(ConversationBaseSchema):
    thread_id: str = Field(min_length=1)
    telegram_chat_id: int | None = None
    project: str = Field(min_length=1)
    issue_id: str | None = None
    phase: ConversationPhase = ConversationPhase.STARTED
    iteration_count: int = Field(default=0, ge=0)
    brief_version: int = Field(default=0, ge=0)
    last_pm_message: str | None = None
    pending_questions: list[str] = Field(default_factory=list)
    approved: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationThread(ConversationBaseSchema):
    thread_id: str = Field(default_factory=_thread_id)
    topic: str = Field(min_length=1)
    status: ConversationStatus = ConversationStatus.ACTIVE
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    messages: list[ConversationMessage] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    founder_pm_state: FounderPMConversationState | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
