from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from lummevia_queue.schemas import TaskPriority, TaskQueue, TaskQueueItem, TaskQueueStatus


class TaskQueueRegistry:
    _default_instance: ClassVar["TaskQueueRegistry" | None] = None

    def __init__(self) -> None:
        self._queues: dict[str, TaskQueue] = {}

    @classmethod
    def default(cls) -> "TaskQueueRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._queues.clear()

    def create_queue(
        self,
        *,
        project: str,
        workflow_run_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> TaskQueue:
        queue = TaskQueue(
            project=project,
            workflow_run_id=workflow_run_id,
            metadata=metadata or {},
        )
        self._queues[queue.queue_id] = queue
        return queue

    def add_item(self, queue_id: str, item: TaskQueueItem) -> TaskQueueItem:
        queue = self._queues[queue_id]
        updated_queue = queue.model_copy(update={"items": [*queue.items, item]})
        self._queues[queue_id] = self._refresh_queue(updated_queue)
        return next(
            stored_item
            for stored_item in self._queues[queue_id].items
            if stored_item.queue_item_id == item.queue_item_id
        )

    def get_queue(self, queue_id: str) -> TaskQueue | None:
        queue = self._queues.get(queue_id)
        if queue is None:
            return None
        refreshed = self._refresh_queue(queue)
        self._queues[queue_id] = refreshed
        return refreshed

    def list_queues(self) -> list[TaskQueue]:
        queues: list[TaskQueue] = []
        for queue_id in sorted(self._queues):
            queue = self.get_queue(queue_id)
            if queue is not None:
                queues.append(queue)
        return queues

    def update_item_status(
        self,
        queue_id: str,
        queue_item_id: str,
        status: TaskQueueStatus,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> TaskQueueItem:
        queue = self._queues[queue_id]
        updated_items = []
        for item in queue.items:
            if item.queue_item_id == queue_item_id:
                updated_items.append(
                    item.model_copy(
                        update={
                            "status": status,
                            "updated_at": datetime.now(UTC),
                            "metadata": {
                                **item.metadata,
                                **(metadata or {}),
                            },
                        }
                    )
                )
            else:
                updated_items.append(item)
        updated_queue = self._refresh_queue(queue.model_copy(update={"items": updated_items}))
        self._queues[queue_id] = updated_queue
        return next(item for item in updated_queue.items if item.queue_item_id == queue_item_id)

    def list_ready_items(self, queue_id: str) -> list[TaskQueueItem]:
        queue = self.get_queue(queue_id)
        if queue is None:
            return []
        return [
            item for item in queue.items if item.status == TaskQueueStatus.READY
        ]

    def mark_completed(self, queue_id: str, queue_item_id: str) -> TaskQueueItem:
        return self.update_item_status(
            queue_id,
            queue_item_id,
            TaskQueueStatus.COMPLETED,
        )

    def _refresh_queue(self, queue: TaskQueue) -> TaskQueue:
        item_by_task_id = {item.task_id: item for item in queue.items}
        running_exists = any(item.status == TaskQueueStatus.RUNNING for item in queue.items)
        refreshed_items: list[TaskQueueItem] = []
        for item in queue.items:
            if item.status in {
                TaskQueueStatus.RUNNING,
                TaskQueueStatus.COMPLETED,
                TaskQueueStatus.FAILED,
                TaskQueueStatus.CANCELLED,
            }:
                refreshed_items.append(item)
                continue
            dependencies_completed = all(
                item_by_task_id.get(dependency) is not None
                and item_by_task_id[dependency].status == TaskQueueStatus.COMPLETED
                for dependency in item.dependencies
            )
            if item.dependencies and not dependencies_completed:
                next_status = TaskQueueStatus.BLOCKED
            elif running_exists:
                next_status = item.status if item.status == TaskQueueStatus.READY else TaskQueueStatus.QUEUED
            else:
                next_status = TaskQueueStatus.READY
            next_updated_at = datetime.now(UTC) if next_status != item.status else item.updated_at
            refreshed_items.append(
                item.model_copy(
                    update={
                        "status": next_status,
                        "updated_at": next_updated_at,
                    }
                )
            )
        return queue.model_copy(update={"items": refreshed_items})


def queue_priority_weight(priority: TaskPriority) -> int:
    return {
        TaskPriority.CRITICAL: 0,
        TaskPriority.HIGH: 1,
        TaskPriority.NORMAL: 2,
        TaskPriority.LOW: 3,
    }[priority]
