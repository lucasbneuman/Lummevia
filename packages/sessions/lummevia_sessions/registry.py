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
        self._persistence = None

    @classmethod
    def default(cls) -> "SessionRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._sessions.clear()

    def configure_persistence(self, persistence) -> None:
        self._persistence = persistence

    def rehydrate(self, sessions: list[TaskExecutionSession]) -> None:
        self._sessions = {session.session_id: session for session in sessions}

    def create_session(
        self,
        *,
        task_id: str,
        project: str,
        issue_id: str,
        queue_id: str | None = None,
        queue_item_id: str | None = None,
        workspace_id: str | None = None,
        branch_name: str | None = None,
        worktree_path: str | None = None,
        lock_ids: list[str] | None = None,
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
            workspace_id=workspace_id,
            branch_name=branch_name,
            worktree_path=worktree_path,
            lock_ids=lock_ids or [],
            role=role,
            mode=mode,
            status=SessionStatus.CREATED,
            health_status=str((metadata or {}).get("health_status", "WAITING")),
            watchdog_id=(metadata or {}).get("watchdog_id"),
            retry_attempts=int((metadata or {}).get("retry_attempts", 0)),
            recovery_history=list((metadata or {}).get("recovery_history", [])),
            started_at=timestamp,
            updated_at=timestamp,
            metadata=metadata or {},
        )
        self._sessions[session.session_id] = session
        self._persist_session(session)
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
        self._persist_session(updated)
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
        self._persist_session(updated)
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
                "retry_attempts": int(merged_metadata.get("retry_attempts", session.retry_attempts)),
                "watchdog_id": merged_metadata.get("watchdog_id", session.watchdog_id),
                "health_status": str(merged_metadata.get("health_status", session.health_status)),
                "recovery_history": list(
                    merged_metadata.get("recovery_history", session.recovery_history)
                ),
                "updated_at": datetime.now(UTC),
                "completed_at": datetime.now(UTC) if is_terminal else None,
                "metadata": merged_metadata,
            }
        )
        self._sessions[session_id] = updated
        self._persist_session(updated)
        return self.add_event(
            session_id,
            type="STATUS_UPDATED",
            message=f"Session status updated to {status.value}.",
            metadata={
                "status": status.value,
                "role": updated.role.value,
                "mode": updated.mode.value,
                "attempts": updated.attempts,
                "retry_attempts": updated.retry_attempts,
                "health_status": updated.health_status,
                "watchdog_id": updated.watchdog_id,
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

    def save_session(self, session: TaskExecutionSession) -> TaskExecutionSession:
        self._sessions[session.session_id] = session
        self._persist_session(session)
        return session

    def _persist_session(self, session: TaskExecutionSession) -> None:
        if self._persistence is None:
            return
        try:
            self._persistence.save_session(session)
        except Exception:
            return
