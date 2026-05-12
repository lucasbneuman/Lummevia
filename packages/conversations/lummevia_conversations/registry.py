from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from lummevia_conversations.schemas import (
    AuthorType,
    ConversationMessage,
    ConversationStatus,
    ConversationThread,
)


class ConversationThreadNotFoundError(KeyError):
    """Raised when a conversation thread does not exist in the registry."""


class ConversationRegistry:
    _default_instance: ClassVar["ConversationRegistry" | None] = None

    def __init__(self) -> None:
        self._threads: dict[str, ConversationThread] = {}
        self._persistence = None

    @classmethod
    def default(cls) -> "ConversationRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._threads.clear()

    def configure_persistence(self, persistence) -> None:
        self._persistence = persistence

    def rehydrate(self, threads: list[ConversationThread]) -> None:
        self._threads = {thread.thread_id: thread for thread in threads}

    def create_thread(
        self,
        *,
        topic: str,
        project: str,
        issue_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationThread:
        thread = ConversationThread(
            topic=topic,
            project=project,
            issue_id=issue_id,
            metadata=metadata or {},
        )
        self._threads[thread.thread_id] = thread
        self._persist_thread(thread)
        return thread

    def add_message(
        self,
        thread_id: str,
        *,
        role: str,
        author_type: AuthorType,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationThread:
        thread = self.get_thread(thread_id)
        updated = thread.model_copy(
            update={
                "messages": [
                    *thread.messages,
                    ConversationMessage(
                        role=role,
                        author_type=author_type,
                        content=content,
                        metadata=metadata or {},
                    ),
                ],
                "updated_at": datetime.now(UTC),
            }
        )
        self._threads[thread_id] = updated
        self._persist_thread(updated)
        return updated

    def update_thread_status(
        self,
        thread_id: str,
        status: ConversationStatus,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationThread:
        thread = self.get_thread(thread_id)
        merged_metadata = dict(thread.metadata)
        merged_metadata.update(metadata or {})
        updated = thread.model_copy(
            update={
                "status": status,
                "updated_at": datetime.now(UTC),
                "metadata": merged_metadata,
            }
        )
        self._threads[thread_id] = updated
        return updated

    def get_thread(self, thread_id: str) -> ConversationThread:
        try:
            return self._threads[thread_id]
        except KeyError as exc:
            raise ConversationThreadNotFoundError(
                f"Conversation thread '{thread_id}' not found."
            ) from exc

    def list_threads(self) -> list[ConversationThread]:
        return sorted(
            self._threads.values(),
            key=lambda thread: thread.updated_at,
            reverse=True,
        )

    def close_thread(self, thread_id: str) -> ConversationThread:
        return self.update_thread_status(thread_id, ConversationStatus.CLOSED)

    def _persist_thread(self, thread: ConversationThread) -> None:
        if self._persistence is None:
            return
        try:
            self._persistence.save_thread(thread)
        except Exception:
            return
