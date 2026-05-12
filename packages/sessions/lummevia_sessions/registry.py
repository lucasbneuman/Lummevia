from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import uuid4

from lummevia_core import AgentRole
from lummevia_kilo import KiloExecutionMode
from lummevia_sessions.schemas import (
    SessionEvent,
    SessionOutput,
    SessionStatus,
    TaskExecutionSession,
)


class SessionRegistry:
    _default_instance: ClassVar["SessionRegistry" | None] = None

    def __init__(self) -> None:
        self._sessions: dict[str, TaskExecutionSession] = {}

    @classmethod
    def default(cls) -> "SessionRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._sessions.clear()

    def create_session(
        self,
        *,
        task_id: str,
        project: str,
        issue_id: str,
        queue_id: str | None = None,
        queue_item_id: str | None = None,
        role: AgentRole,
        mode: KiloExecutionMode,
        metadata: dict[str, Any] | None = None,
    ) -> TaskExecutionSession:
        timestamp = datetime.now(UTC)
        session = TaskExecutionSession(
            session_id=f"session-{uuid4()}",
            task_id=task_id,
            project=project,
            issue_id=issue_id,
            queue_id=queue_id,
            queue_item_id=queue_item_id,
            role=role,
            mode=mode,
            status=SessionStatus.CREATED,
            started_at=timestamp,
            updated_at=timestamp,
            metadata=metadata or {},
        )
        self._sessions[session.session_id] = session
        return session

    def add_event(
        self,
        session_id: str,
        *,
        type: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> TaskExecutionSession:
        session = self._sessions[session_id]
        updated = session.model_copy(
            update={
                "events": [
                    *session.events,
                    SessionEvent(
                        event_id=f"session-event-{uuid4()}",
                        type=type,
                        message=message,
                        metadata=metadata or {},
                    ),
                ],
                "updated_at": datetime.now(UTC),
            }
        )
        self._sessions[session_id] = updated
        return updated

    def add_output(
        self,
        session_id: str,
        *,
        output_type: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> TaskExecutionSession:
        session = self._sessions[session_id]
        updated = session.model_copy(
            update={
                "outputs": [
                    *session.outputs,
                    SessionOutput(
                        output_id=f"session-output-{uuid4()}",
                        output_type=output_type,
                        content=content,
                        metadata=metadata or {},
                    ),
                ],
                "updated_at": datetime.now(UTC),
            }
        )
        self._sessions[session_id] = updated
        return updated

    def update_status(
        self,
        session_id: str,
        *,
        status: SessionStatus,
        role: AgentRole | None = None,
        mode: KiloExecutionMode | None = None,
        attempts: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskExecutionSession:
        session = self._sessions[session_id]
        merged_metadata = dict(session.metadata)
        merged_metadata.update(metadata or {})
        is_terminal = status in {
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.CANCELLED,
        }
        updated = session.model_copy(
            update={
                "status": status,
                "role": role or session.role,
                "mode": mode or session.mode,
                "attempts": attempts if attempts is not None else session.attempts,
                "updated_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC) if is_terminal else None,
                "metadata": merged_metadata,
            }
        )
        self._sessions[session_id] = updated
        return self.add_event(
            session_id,
            type="STATUS_UPDATED",
            message=f"Session status updated to {status.value}.",
            metadata={
                "status": status.value,
                "role": updated.role.value,
                "mode": updated.mode.value,
                "attempts": updated.attempts,
            },
        )

    def get_session(self, session_id: str) -> TaskExecutionSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[TaskExecutionSession]:
        return sorted(
            self._sessions.values(),
            key=lambda session: session.updated_at,
            reverse=True,
        )
