from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from lummevia_conversations import (
    AuthorType,
    ConversationRegistry,
    ConversationThread,
    ConversationThreadNotFoundError,
)


router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationMessageRequest(BaseModel):
    role: str = Field(min_length=1)
    author_type: AuthorType
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _get_conversation_registry() -> ConversationRegistry:
    return ConversationRegistry.default()


@router.get("", response_model=list[ConversationThread])
def list_conversations() -> list[ConversationThread]:
    return _get_conversation_registry().list_threads()


@router.get("/{thread_id}", response_model=ConversationThread)
def get_conversation(thread_id: str) -> ConversationThread:
    try:
        return _get_conversation_registry().get_thread(thread_id)
    except ConversationThreadNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.args[0],
        ) from exc


@router.post("/{thread_id}/message", response_model=ConversationThread)
def add_conversation_message(
    thread_id: str,
    request: ConversationMessageRequest,
) -> ConversationThread:
    try:
        return _get_conversation_registry().add_message(
            thread_id,
            role=request.role,
            author_type=request.author_type,
            content=request.content,
            metadata=request.metadata,
        )
    except ConversationThreadNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.args[0],
        ) from exc
