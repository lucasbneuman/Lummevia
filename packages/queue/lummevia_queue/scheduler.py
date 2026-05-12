from __future__ import annotations

from lummevia_queue.registry import TaskQueueRegistry, queue_priority_weight
from lummevia_queue.schemas import TaskQueueItem, TaskQueueStatus


class TaskQueueScheduler:
    def __init__(self, registry: TaskQueueRegistry | None = None) -> None:
        self.registry = registry or TaskQueueRegistry.default()

    def detect_ready_items(self, queue_id: str) -> list[TaskQueueItem]:
        return self.registry.list_ready_items(queue_id)

    def select_next_item(self, queue_id: str) -> TaskQueueItem | None:
        queue = self.registry.get_queue(queue_id)
        if queue is None:
            return None
        if any(item.status == TaskQueueStatus.RUNNING for item in queue.items):
            return None
        ready_items = [item for item in queue.items if item.status == TaskQueueStatus.READY]
        if not ready_items:
            return None
        return sorted(
            ready_items,
            key=lambda item: (
                queue_priority_weight(item.priority),
                item.created_at,
                item.queue_item_id,
            ),
        )[0]

    def start_next_item(self, queue_id: str) -> TaskQueueItem | None:
        next_item = self.select_next_item(queue_id)
        if next_item is None:
            return None
        return self.registry.update_item_status(
            queue_id,
            next_item.queue_item_id,
            TaskQueueStatus.RUNNING,
        )
