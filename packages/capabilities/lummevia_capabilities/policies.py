from __future__ import annotations

from lummevia_capabilities.schemas import (
    AllocationRequest,
    AllocationStatus,
    ExecutionCapacity,
)


def evaluate_allocation_request(
    request: AllocationRequest,
    *,
    agent_capability_exists: bool,
    model_capability_exists: bool,
    mode_supported: bool,
    capacities: list[ExecutionCapacity],
    missing_capacities: list[str],
) -> tuple[AllocationStatus, str]:
    if not agent_capability_exists:
        return AllocationStatus.DENIED, f"Agent capability not found for role '{request.role.value}'."
    if not model_capability_exists:
        return AllocationStatus.DENIED, (
            f"Model capability not found for '{request.provider}:{request.model}'."
        )
    if not mode_supported:
        return AllocationStatus.DENIED, (
            f"Mode '{request.mode.value}' is not supported for role '{request.role.value}'."
        )
    if missing_capacities:
        return AllocationStatus.DENIED, (
            "Missing execution capacity for "
            + ", ".join(sorted(missing_capacities))
            + "."
        )
    exhausted = [
        f"{capacity.resource_type.value}:{capacity.resource_id}"
        for capacity in capacities
        if capacity.used_slots >= capacity.max_slots
    ]
    if exhausted:
        return AllocationStatus.WAITING, (
            "No slots available for " + ", ".join(sorted(exhausted)) + "."
        )
    return AllocationStatus.GRANTED, "Allocation granted."
