from __future__ import annotations

from typing import Any
from uuid import uuid4

from lummevia_capabilities import (
    AllocationRequest,
    AllocationResult,
    AllocationStatus,
    CapabilityAllocator,
)
from lummevia_core import AgentRole, TaskPackage
from lummevia_kilo import KiloExecutionMode
from lummevia_queue import TaskQueueRegistry, TaskQueueStatus
from model_router import AgentRole as RouterAgentRole
from model_router import RoutingRequest, resolve_model

from lummevia_runtime.state import RuntimeState


ROLE_TO_ROUTER_ROLE = {
    AgentRole.PM: RouterAgentRole.PM,
    AgentRole.PO: RouterAgentRole.PO,
    AgentRole.DEV: RouterAgentRole.DEV,
    AgentRole.QA: RouterAgentRole.QA,
    AgentRole.QC: RouterAgentRole.QC,
}


def request_step_allocation(
    state: RuntimeState,
    *,
    step_name: str,
    role: AgentRole,
    mode: KiloExecutionMode,
    task_package: TaskPackage,
) -> AllocationResult:
    router_role = ROLE_TO_ROUTER_ROLE[role]
    model_resolution = resolve_model(
        RoutingRequest(
            role=router_role,
            project=state.run.project,
            environment=str(state.metadata.get("environment", "")).strip() or None,
        )
    )
    queue_item_id = state.metadata.get("current_queue_item_id")
    allocation_request = AllocationRequest(
        request_id=f"allocation-request-{uuid4()}",
        project=state.run.project,
        issue_id=state.run.issue_id,
        task_id=task_package.task_id,
        role=role,
        mode=mode,
        provider=model_resolution.provider.value,
        model=model_resolution.model,
        required_resources=[],
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "queue_id": state.metadata.get("queue_id"),
            "queue_item_id": queue_item_id,
            "workspace_id": state.metadata.get("workspace_id"),
            "branch_name": state.metadata.get("branch_name"),
            "worktree_path": state.metadata.get("worktree_path"),
        },
    )
    allocation = CapabilityAllocator.default().request_allocation(allocation_request)
    sync_allocation_to_runtime_metadata(state, allocation=allocation, step_name=step_name)
    if queue_item_id:
        sync_allocation_to_queue_item(
            state,
            queue_item_id=str(queue_item_id),
            allocation=allocation,
        )
    return allocation


def release_step_allocation(state: RuntimeState, *, allocation_id: str | None) -> AllocationResult | None:
    if not allocation_id:
        return None
    return CapabilityAllocator.default().release_allocation(allocation_id)


def sync_allocation_to_runtime_metadata(
    state: RuntimeState,
    *,
    allocation: AllocationResult,
    step_name: str,
) -> None:
    allocation_metadata = _build_allocation_metadata(allocation)
    state.metadata.update(allocation_metadata)
    state.metadata.setdefault("allocation_by_step", {})[step_name] = allocation_metadata
    state.metadata.setdefault("allocation_results", {})[allocation.allocation_id] = allocation.model_dump(
        mode="json"
    )


def sync_allocation_to_queue_item(
    state: RuntimeState,
    *,
    queue_item_id: str,
    allocation: AllocationResult,
) -> None:
    queue_id = str(state.metadata.get("queue_id", "")).strip()
    if not queue_id:
        return
    queue = TaskQueueRegistry.default().get_queue(queue_id)
    if queue is None:
        return
    queue_item = next(
        (item for item in queue.items if item.queue_item_id == queue_item_id),
        None,
    )
    if queue_item is None:
        return
    TaskQueueRegistry.default().update_item_status(
        queue_id,
        queue_item_id,
        queue_item.status,
        metadata={
            **queue_item.metadata,
            "allocation_id": allocation.allocation_id,
            "allocation_status": allocation.status.value,
            "allocation_reason": allocation.reason,
            "capacity_id": _first_allocated_value(allocation, "capacity_id"),
            "allocated_resources": allocation.allocated_resources,
        },
    )
    state.metadata["task_queue"] = TaskQueueRegistry.default().get_queue(queue_id).model_dump(mode="json")


def build_allocation_metadata_for_kilo(state: RuntimeState) -> dict[str, Any]:
    return {
        "allocation_id": state.metadata.get("allocation_id"),
        "allocation_status": state.metadata.get("allocation_status"),
        "allocation_reason": state.metadata.get("allocation_reason"),
        "capacity_id": state.metadata.get("capacity_id"),
        "capacity_used_slots": state.metadata.get("capacity_used_slots"),
        "capacity_max_slots": state.metadata.get("capacity_max_slots"),
        "allocated_resources": state.metadata.get("allocated_resources", []),
        "allocated_resources_count": state.metadata.get("allocated_resources_count", 0),
    }


def mark_task_waiting_for_allocation(
    state: RuntimeState,
    *,
    allocation: AllocationResult,
) -> None:
    queue_id = str(state.metadata.get("queue_id", "")).strip()
    queue_item_id = str(state.metadata.get("current_queue_item_id", "")).strip()
    if not queue_id or not queue_item_id:
        return
    TaskQueueRegistry.default().update_item_status(
        queue_id,
        queue_item_id,
        TaskQueueStatus.BLOCKED if allocation.status == AllocationStatus.WAITING else TaskQueueStatus.QUEUED,
        metadata={
            "allocation_id": allocation.allocation_id,
            "allocation_status": allocation.status.value,
            "allocation_reason": allocation.reason,
        },
    )
    state.metadata["task_queue"] = TaskQueueRegistry.default().get_queue(queue_id).model_dump(mode="json")


def _build_allocation_metadata(allocation: AllocationResult) -> dict[str, Any]:
    return {
        "allocation_id": allocation.allocation_id,
        "allocation_status": allocation.status.value,
        "allocation_reason": allocation.reason,
        "capacity_id": _first_allocated_value(allocation, "capacity_id"),
        "capacity_used_slots": _first_allocated_value(allocation, "used_slots"),
        "capacity_max_slots": _first_allocated_value(allocation, "max_slots"),
        "allocated_resources": allocation.allocated_resources,
        "allocated_resources_count": len(allocation.allocated_resources),
    }


def _first_allocated_value(allocation: AllocationResult, key: str) -> Any:
    if not allocation.allocated_resources:
        return None
    return allocation.allocated_resources[0].get(key)
