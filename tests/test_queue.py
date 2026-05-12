from fastapi.testclient import TestClient

from lummevia_core import AgentRole
from lummevia_queue import (
    TaskPriority,
    TaskQueueItem,
    TaskQueueRegistry,
    TaskQueueScheduler,
    TaskQueueStatus,
)
from main import app


client = TestClient(app)


def _build_item(
    *,
    task_id: str,
    issue_id: str = "OS-700",
    priority: TaskPriority = TaskPriority.NORMAL,
    status: TaskQueueStatus = TaskQueueStatus.QUEUED,
    dependencies: list[str] | None = None,
    created_at: str | None = None,
) -> TaskQueueItem:
    payload = {
        "queue_item_id": f"queue-item-{task_id}",
        "task_id": task_id,
        "project": "lummevia-os",
        "issue_id": issue_id,
        "priority": priority,
        "status": status,
        "dependencies": dependencies or [],
        "assigned_role": AgentRole.DEV,
        "mode": "CODE",
        "metadata": {},
    }
    if created_at is not None:
        payload["created_at"] = created_at
        payload["updated_at"] = created_at
    return TaskQueueItem.model_validate(payload)


def test_queue_registry_creates_adds_and_lists_queue_items() -> None:
    registry = TaskQueueRegistry()
    queue = registry.create_queue(
        project="lummevia-os",
        workflow_run_id="run-700",
    )
    item = registry.add_item(
        queue.queue_id,
        _build_item(task_id="OS-700-T1"),
    )

    recovered = registry.get_queue(queue.queue_id)

    assert recovered is not None
    assert recovered.queue_id == queue.queue_id
    assert len(recovered.items) == 1
    assert recovered.items[0].queue_item_id == item.queue_item_id
    assert recovered.items[0].task_id == item.task_id
    assert recovered.items[0].status == TaskQueueStatus.READY
    assert registry.list_queues() == [recovered]


def test_queue_registry_detects_blocked_and_ready_items_from_dependencies() -> None:
    registry = TaskQueueRegistry()
    queue = registry.create_queue(
        project="lummevia-os",
        workflow_run_id="run-701",
    )
    first = registry.add_item(queue.queue_id, _build_item(task_id="OS-701-T1"))
    second = registry.add_item(
        queue.queue_id,
        _build_item(
            task_id="OS-701-T2",
            dependencies=[first.task_id],
        ),
    )

    refreshed = registry.get_queue(queue.queue_id)
    assert refreshed is not None

    first_status = next(item.status for item in refreshed.items if item.task_id == first.task_id)
    second_status = next(item.status for item in refreshed.items if item.task_id == second.task_id)

    assert first_status == TaskQueueStatus.READY
    assert second_status == TaskQueueStatus.BLOCKED
    assert [item.task_id for item in registry.list_ready_items(queue.queue_id)] == [first.task_id]


def test_scheduler_selects_next_item_by_priority_then_created_at() -> None:
    registry = TaskQueueRegistry()
    queue = registry.create_queue(
        project="lummevia-os",
        workflow_run_id="run-702",
    )
    registry.add_item(
        queue.queue_id,
        _build_item(
            task_id="OS-702-T1",
            priority=TaskPriority.NORMAL,
            created_at="2026-05-12T10:00:00Z",
        ),
    )
    expected = registry.add_item(
        queue.queue_id,
        _build_item(
            task_id="OS-702-T2",
            priority=TaskPriority.CRITICAL,
            created_at="2026-05-12T11:00:00Z",
        ),
    )
    registry.add_item(
        queue.queue_id,
        _build_item(
            task_id="OS-702-T3",
            priority=TaskPriority.CRITICAL,
            created_at="2026-05-12T12:00:00Z",
        ),
    )

    scheduler = TaskQueueScheduler(registry)
    next_item = scheduler.select_next_item(queue.queue_id)

    assert next_item is not None
    assert next_item.task_id == expected.task_id


def test_mark_completed_unlocks_dependent_items() -> None:
    registry = TaskQueueRegistry()
    queue = registry.create_queue(
        project="lummevia-os",
        workflow_run_id="run-703",
    )
    first = registry.add_item(queue.queue_id, _build_item(task_id="OS-703-T1"))
    registry.add_item(
        queue.queue_id,
        _build_item(
            task_id="OS-703-T2",
            dependencies=[first.task_id],
        ),
    )

    registry.mark_completed(queue.queue_id, first.queue_item_id)

    ready_items = registry.list_ready_items(queue.queue_id)
    statuses = {
        item.task_id: item.status
        for item in registry.get_queue(queue.queue_id).items
    }

    assert statuses[first.task_id] == TaskQueueStatus.COMPLETED
    assert statuses["OS-703-T2"] == TaskQueueStatus.READY
    assert [item.task_id for item in ready_items] == ["OS-703-T2"]


def test_queue_endpoints_list_queue_and_ready_items() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-704"},
    )
    assert runtime_response.status_code == 200
    queue_id = runtime_response.json()["metadata"]["queue_id"]

    list_response = client.get("/queues")
    assert list_response.status_code == 200
    assert any(queue["queue_id"] == queue_id for queue in list_response.json())

    get_response = client.get(f"/queues/{queue_id}")
    assert get_response.status_code == 200
    assert get_response.json()["queue_id"] == queue_id

    ready_response = client.get(f"/queues/{queue_id}/ready")
    assert ready_response.status_code == 200
    assert all(item["status"] == "READY" for item in ready_response.json())
