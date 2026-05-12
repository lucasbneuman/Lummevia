from __future__ import annotations

from lummevia_sessions import TaskExecutionSession

from lummevia_persistence.repositories.base import SnapshotRepository


class SessionSnapshotRepository(SnapshotRepository):
    entity_type = "session"

    def save_session(self, session: TaskExecutionSession):
        return self.save_snapshot(
            entity_type=self.entity_type,
            entity_id=session.session_id,
            payload=session.model_dump(mode="json"),
            metadata={
                "project": session.project,
                "issue_id": session.issue_id,
                "task_id": session.task_id,
                "status": session.status.value,
            },
        )

    def list_sessions(self) -> list[TaskExecutionSession]:
        return [
            TaskExecutionSession.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.entity_type)
        ]
