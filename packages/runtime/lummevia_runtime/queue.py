from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from lummevia_core import AgentRole, TaskPackage
from lummevia_kilo import KiloExecutionMode, resolve_kilo_mode
from lummevia_queue import (
    TaskPriority,
    TaskQueueItem,
    TaskQueueRegistry,
    TaskQueueScheduler,
    TaskQueueStatus,
)

from lummevia_runtime.state import RuntimeState
from lummevia_runtime.resources import allocate_workspace_for_queue_item
from lummevia_runtime.supervisor import (
    complete_queue_item_watchdog,
    heartbeat_queue_item_watchdog,
    record_supervisor_event,
    register_queue_item_watchdog,
)
from lummevia_supervisor import ExecutionHealthStatus


def initialize_task_queue(
    state: RuntimeState,
    *,
    task_packages: list[TaskPackage],
) -> None:
    registry = TaskQueueRegistry.default()
    queue = registry.create_queue(
        project=state.run.project,
        workflow_run_id=state.run.run_id,
        metadata={
            "issue_id": state.run.issue_id,
            "created_from": "po_task_packages",
        },
    )
    _record_queue_event(
        state,
        event_type="QUEUE_CREATED",
        title=f"Queue {queue.queue_id} created",
        description=f"Task queue created for workflow run {state.run.run_id}.",
        metadata={"queue_id": queue.queue_id},
    )
    for task_package in task_packages:
        queue_item = registry.add_item(
            queue.queue_id,
            TaskQueueItem(
                task_id=task_package.task_id,
                project=task_package.project,
                issue_id=task_package.issue_id,
                priority=_resolve_task_priority(task_package),
                status=TaskQueueStatus.QUEUED,
                dependencies=_resolve_dependencies(task_package),
                assigned_role=AgentRole.DEV,
                mode=resolve_kilo_mode(AgentRole.DEV),
                metadata={
                    "title": task_package.title,
                    "health_status": ExecutionHealthStatus.WAITING.value,
                    "recovery_action_id": None,
                    "dead_letter_id": None,
                    "retry_attempts": 0,
                    "last_heartbeat_at": None,
                    "watchdog_id": None,
                    "allocation_id": None,
                    "allocation_status": None,
                    "allocation_reason": None,
                    "strategy_id": state.metadata.get("strategy_id"),
                    "risk_level": state.metadata.get("risk_level"),
                    "execution_mode": state.metadata.get("execution_mode"),
                },
            ),
        )
        _record_queue_event(
            state,
            event_type="TASK_QUEUED",
            title=f"Task {task_package.task_id} queued",
            description=f"TaskPackage {task_package.task_id} entered queue {queue.queue_id}.",
            metadata={
                "queue_id": queue.queue_id,
                "queue_item_id": queue_item.queue_item_id,
                "task_id": task_package.task_id,
                "task_priority": queue_item.priority.value,
                "dependencies": queue_item.dependencies,
            },
        )
    sync_task_queue_state(state, queue_id=queue.queue_id)
    for queue_item in registry.get_queue(queue.queue_id).items:
        if queue_item.status == TaskQueueStatus.READY:
            _record_queue_event(
                state,
                event_type="TASK_READY",
                title=f"Task {queue_item.task_id} ready",
                description=f"Task {queue_item.task_id} is ready for execution.",
                metadata={
                    "queue_id": queue.queue_id,
                    "queue_item_id": queue_item.queue_item_id,
                    "task_id": queue_item.task_id,
                },
            )
    started_item = TaskQueueScheduler(registry).start_next_item(queue.queue_id)
    if started_item is not None:
        task_package = next(
            (
                item
                for item in task_packages
                if item.task_id == started_item.task_id
            ),
            None,
        )
        if task_package is not None:
            allocate_workspace_for_queue_item(
                state,
                queue_item=started_item,
                task_package=task_package,
            )
        watchdog_id = register_queue_item_watchdog(
            state,
            queue_id=queue.queue_id,
            queue_item_id=started_item.queue_item_id,
            task_id=started_item.task_id,
        )
        heartbeat_queue_item_watchdog(state, queue_item_id=started_item.queue_item_id)
        _record_queue_event(
            state,
            event_type="TASK_STARTED",
            title=f"Task {started_item.task_id} started",
            description=f"Task {started_item.task_id} became the active runtime item.",
            metadata={
                "queue_id": queue.queue_id,
                "queue_item_id": started_item.queue_item_id,
                "task_id": started_item.task_id,
                "watchdog_id": watchdog_id,
            },
        )
        record_supervisor_event(
            state,
            event_type="QUEUE_ITEM_ACTIVATED",
            status=ExecutionHealthStatus.RUNNING,
            metadata={
                "queue_id": queue.queue_id,
                "queue_item_id": started_item.queue_item_id,
                "task_id": started_item.task_id,
                "watchdog_id": watchdog_id,
            },
            queue_item_id=started_item.queue_item_id,
        )
    sync_task_queue_state(state, queue_id=queue.queue_id)


def mark_current_queue_item_completed(state: RuntimeState) -> None:
    queue_id = _get_queue_id(state)
    queue_item_id = _get_queue_item_id(state)
    if queue_id is None or queue_item_id is None:
        return
    registry = TaskQueueRegistry.default()
    completed_item = registry.mark_completed(queue_id, queue_item_id)
    complete_queue_item_watchdog(state, queue_item_id=queue_item_id)
    _record_queue_event(
        state,
        event_type="TASK_COMPLETED",
        title=f"Task {completed_item.task_id} completed",
        description=f"Task {completed_item.task_id} completed its current queue execution.",
        metadata={
            "queue_id": queue_id,
            "queue_item_id": queue_item_id,
            "task_id": completed_item.task_id,
        },
    )
    record_supervisor_event(
        state,
        event_type="TASK_REQUEUED" if completed_item.status == TaskQueueStatus.READY else "QUEUE_ITEM_COMPLETED",
        status=ExecutionHealthStatus.HEALTHY,
        metadata={
            "queue_id": queue_id,
            "queue_item_id": queue_item_id,
            "task_id": completed_item.task_id,
        },
        queue_item_id=queue_item_id,
    )
    queue = registry.get_queue(queue_id)
    if queue is not None:
        for item in queue.items:
            if item.status == TaskQueueStatus.READY and item.queue_item_id != queue_item_id:
                _record_queue_event(
                    state,
                    event_type="TASK_READY",
                    title=f"Task {item.task_id} ready",
                    description=f"Task {item.task_id} is ready after dependency resolution.",
                    metadata={
                        "queue_id": queue_id,
                        "queue_item_id": item.queue_item_id,
                        "task_id": item.task_id,
                    },
                )
    sync_task_queue_state(state, queue_id=queue_id)


def sync_task_queue_state(state: RuntimeState, *, queue_id: str | None = None) -> None:
    resolved_queue_id = queue_id or _get_queue_id(state)
    if resolved_queue_id is None:
        return
    queue = TaskQueueRegistry.default().get_queue(resolved_queue_id)
    if queue is None:
        return
    ready_items = [item for item in queue.items if item.status == TaskQueueStatus.READY]
    blocked_items = [item for item in queue.items if item.status == TaskQueueStatus.BLOCKED]
    completed_items = [item for item in queue.items if item.status == TaskQueueStatus.COMPLETED]
    previous_queue_item_id = state.metadata.get("current_queue_item_id")
    current_item = next(
        (item for item in queue.items if item.status == TaskQueueStatus.RUNNING),
        None,
    )
    if current_item is None and previous_queue_item_id:
        current_item = next(
            (
                item
                for item in queue.items
                if item.queue_item_id == previous_queue_item_id
            ),
            None,
        )
    state.metadata["queue_id"] = queue.queue_id
    state.metadata["task_queue"] = queue.model_dump(mode="json")
    state.metadata["queue_size"] = len(queue.items)
    state.metadata["ready_count"] = len(ready_items)
    state.metadata["blocked_count"] = len(blocked_items)
    state.metadata["completed_count"] = len(completed_items)
    state.metadata["current_queue_item_id"] = current_item.queue_item_id if current_item else None
    state.metadata["current_queue_task_id"] = current_item.task_id if current_item else None


def build_queue_metadata_for_kilo(
    state: RuntimeState,
    *,
    task_package: TaskPackage,
) -> dict[str, Any]:
    queue_snapshot = state.metadata.get("task_queue", {})
    if not isinstance(queue_snapshot, dict):
        queue_snapshot = {}
    queue_item = next(
        (
            item
            for item in queue_snapshot.get("items", [])
            if item.get("task_id") == task_package.task_id
        ),
        None,
    )
    return {
        "queue_id": state.metadata.get("queue_id"),
        "queue_item_id": (
            queue_item.get("queue_item_id")
            if isinstance(queue_item, dict)
            else None
        ),
        "task_priority": (
            queue_item.get("priority")
            if isinstance(queue_item, dict)
            else None
        ),
        "dependencies": (
            queue_item.get("dependencies", [])
            if isinstance(queue_item, dict)
            else []
        ),
        "workspace_id": (
            queue_item.get("metadata", {}).get("workspace_id")
            if isinstance(queue_item, dict)
            else state.metadata.get("workspace_id")
        ),
        "branch_name": (
            queue_item.get("metadata", {}).get("branch_name")
            if isinstance(queue_item, dict)
            else state.metadata.get("branch_name")
        ),
        "worktree_path": (
            queue_item.get("metadata", {}).get("worktree_path")
            if isinstance(queue_item, dict)
            else state.metadata.get("worktree_path")
        ),
        "lock_ids": (
            queue_item.get("metadata", {}).get("lock_ids", [])
            if isinstance(queue_item, dict)
            else state.metadata.get("lock_ids", [])
        ),
        "workspace_status": (
            queue_item.get("metadata", {}).get("workspace_status")
            if isinstance(queue_item, dict)
            else state.metadata.get("workspace_status")
        ),
        "health_status": (
            queue_item.get("metadata", {}).get("health_status")
            if isinstance(queue_item, dict)
            else state.metadata.get("health_status")
        ),
        "watchdog_id": (
            queue_item.get("metadata", {}).get("watchdog_id")
            if isinstance(queue_item, dict)
            else state.metadata.get("watchdog_id")
        ),
        "retry_attempts": (
            queue_item.get("metadata", {}).get("retry_attempts", 0)
            if isinstance(queue_item, dict)
            else state.metadata.get("retry_attempts", 0)
        ),
        "allocation_id": (
            queue_item.get("metadata", {}).get("allocation_id")
            if isinstance(queue_item, dict)
            else state.metadata.get("allocation_id")
        ),
        "allocation_status": (
            queue_item.get("metadata", {}).get("allocation_status")
            if isinstance(queue_item, dict)
            else state.metadata.get("allocation_status")
        ),
        "allocation_reason": (
            queue_item.get("metadata", {}).get("allocation_reason")
            if isinstance(queue_item, dict)
            else state.metadata.get("allocation_reason")
        ),
        "capacity_id": (
            queue_item.get("metadata", {}).get("capacity_id")
            if isinstance(queue_item, dict)
            else state.metadata.get("capacity_id")
        ),
        "allocated_resources": (
            queue_item.get("metadata", {}).get("allocated_resources", [])
            if isinstance(queue_item, dict)
            else state.metadata.get("allocated_resources", [])
        ),
        "strategy_id": (
            queue_item.get("metadata", {}).get("strategy_id")
            if isinstance(queue_item, dict)
            else state.metadata.get("strategy_id")
        ),
        "risk_level": (
            queue_item.get("metadata", {}).get("risk_level")
            if isinstance(queue_item, dict)
            else state.metadata.get("risk_level")
        ),
        "execution_mode": (
            queue_item.get("metadata", {}).get("execution_mode")
            if isinstance(queue_item, dict)
            else state.metadata.get("execution_mode")
        ),
    }


def _resolve_task_priority(task_package: TaskPackage) -> TaskPriority:
    raw_priority = task_package.metadata.get("priority")
    if raw_priority is not None:
        normalized = str(raw_priority).upper()
        if normalized == "LOW":
            return TaskPriority.LOW
        if normalized == "HIGH":
            return TaskPriority.HIGH
        if normalized == "CRITICAL":
            return TaskPriority.CRITICAL
    return TaskPriority.NORMAL


def _resolve_dependencies(task_package: TaskPackage) -> list[str]:
    dependencies = task_package.metadata.get("dependencies", [])
    if not isinstance(dependencies, list):
        return []
    return [str(dependency) for dependency in dependencies if str(dependency).strip()]


def _record_queue_event(
    state: RuntimeState,
    *,
    event_type: str,
    title: str,
    description: str,
    metadata: dict[str, Any],
) -> None:
    state.metadata.setdefault("queue_events", []).append(
        {
            "event_id": f"queue-event-{uuid4()}",
            "workflow_run_id": state.run.run_id,
            "event_type": event_type,
            "title": title,
            "description": description,
            "created_at": datetime.now(UTC).isoformat(),
            "metadata": metadata,
        }
    )


def _get_queue_id(state: RuntimeState) -> str | None:
    queue_id = state.metadata.get("queue_id")
    return str(queue_id) if queue_id else None


def _get_queue_item_id(state: RuntimeState) -> str | None:
    queue_item_id = state.metadata.get("current_queue_item_id")
    return str(queue_item_id) if queue_item_id else None
