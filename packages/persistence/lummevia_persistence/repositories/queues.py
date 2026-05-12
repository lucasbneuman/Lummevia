from __future__ import annotations

from lummevia_queue import TaskQueue

from lummevia_persistence.repositories.base import SnapshotRepository


class QueueSnapshotRepository(SnapshotRepository):
    entity_type = "queue"

    def save_queue(self, queue: TaskQueue):
        return self.save_snapshot(
            entity_type=self.entity_type,
            entity_id=queue.queue_id,
            payload=queue.model_dump(mode="json"),
            metadata={
                "project": queue.project,
                "workflow_run_id": queue.workflow_run_id,
                "item_count": len(queue.items),
            },
        )

    def list_queues(self) -> list[TaskQueue]:
        return [
            TaskQueue.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.entity_type)
        ]
