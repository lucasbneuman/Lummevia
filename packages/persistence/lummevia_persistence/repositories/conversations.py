from __future__ import annotations

from lummevia_conversations import ConversationThread

from lummevia_persistence.repositories.base import SnapshotRepository


class ConversationSnapshotRepository(SnapshotRepository):
    entity_type = "conversation"

    def save_thread(self, thread: ConversationThread):
        return self.save_snapshot(
            entity_type=self.entity_type,
            entity_id=thread.thread_id,
            payload=thread.model_dump(mode="json"),
            metadata={"project": thread.project, "issue_id": thread.issue_id, "status": thread.status.value},
        )

    def list_threads(self) -> list[ConversationThread]:
        return [
            ConversationThread.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.entity_type)
        ]
