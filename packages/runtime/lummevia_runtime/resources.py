from __future__ import annotations

from typing import Any

from lummevia_core import TaskPackage
from lummevia_queue import TaskQueueItem, TaskQueueRegistry
from lummevia_resources import ResourceRegistry, WorkspaceAllocation, WorkspaceAllocator

from lummevia_runtime.state import RuntimeState


def allocate_workspace_for_queue_item(
    state: RuntimeState,
    *,
    queue_item: TaskQueueItem,
    task_package: TaskPackage,
) -> WorkspaceAllocation:
    allocator = WorkspaceAllocator()
    workspace = allocator.allocate_workspace(task_package, queue_item)
    workspace = allocator.mark_workspace_active(
        workspace.workspace_id,
        metadata={
            "run_id": state.run.run_id,
            "issue_id": state.run.issue_id,
            "queue_id": state.metadata.get("queue_id"),
            "queue_item_id": queue_item.queue_item_id,
        },
    )
    queue_id = str(state.metadata.get("queue_id", "")).strip()
    if queue_id:
        TaskQueueRegistry.default().update_item_status(
            queue_id,
            queue_item.queue_item_id,
            queue_item.status,
            metadata=_workspace_metadata_payload(workspace),
        )
    _sync_workspace_to_runtime_metadata(state, workspace)
    return workspace


def release_current_workspace(
    state: RuntimeState,
    *,
    metadata: dict[str, Any] | None = None,
) -> WorkspaceAllocation | None:
    workspace_id = str(state.metadata.get("workspace_id", "")).strip()
    if not workspace_id:
        return None
    allocator = WorkspaceAllocator()
    workspace = allocator.release_workspace(workspace_id, metadata=metadata or {})
    _sync_workspace_to_runtime_metadata(state, workspace)
    return workspace


def refresh_current_workspace(state: RuntimeState) -> WorkspaceAllocation | None:
    workspace_id = str(state.metadata.get("workspace_id", "")).strip()
    if not workspace_id:
        return None
    workspace = ResourceRegistry.default().get_workspace(workspace_id)
    if workspace is None:
        return None
    _sync_workspace_to_runtime_metadata(state, workspace)
    return workspace


def _sync_workspace_to_runtime_metadata(
    state: RuntimeState,
    workspace: WorkspaceAllocation,
) -> None:
    lock_ids = [
        str(lock_id)
        for lock_id in workspace.metadata.get("lock_ids", [])
    ]
    registry = ResourceRegistry.default()
    state.metadata["workspace_id"] = workspace.workspace_id
    state.metadata["branch_name"] = workspace.branch_name
    state.metadata["worktree_path"] = workspace.worktree_path
    state.metadata["workspace_status"] = workspace.status.value
    state.metadata["lock_ids"] = lock_ids
    state.metadata["resource_locks_count"] = len(lock_ids)
    state.metadata["active_locks_count"] = len(registry.list_active_locks())
    state.metadata.setdefault("workspace_allocations", {})[workspace.workspace_id] = (
        workspace.model_dump(mode="json")
    )
    state.metadata["current_workspace"] = workspace.model_dump(mode="json")
    state.metadata["resource_registry"] = {
        "lock_count": len(registry.list_locks()),
        "active_lock_count": len(registry.list_active_locks()),
        "workspace_count": len(registry.list_workspaces()),
    }


def _workspace_metadata_payload(workspace: WorkspaceAllocation) -> dict[str, Any]:
    return {
        "workspace_id": workspace.workspace_id,
        "branch_name": workspace.branch_name,
        "worktree_path": workspace.worktree_path,
        "lock_ids": workspace.metadata.get("lock_ids", []),
        "workspace_status": workspace.status.value,
    }
