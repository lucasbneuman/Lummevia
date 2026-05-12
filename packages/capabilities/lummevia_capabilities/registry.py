from __future__ import annotations

from typing import Any, ClassVar

from lummevia_core import AgentRole
from lummevia_kilo import KiloExecutionMode
from lummevia_queue import TaskPriority
from lummevia_resources import ResourceType
from model_router import AgentRole as RouterAgentRole
from model_router import RoutingRequest, resolve_model

from lummevia_capabilities.policies import evaluate_allocation_request
from lummevia_capabilities.schemas import (
    AgentCapability,
    AllocationRequest,
    AllocationResult,
    AllocationStatus,
    ExecutionCapacity,
    ModelCapability,
)


def _capacity_key(resource_type: ResourceType, resource_id: str) -> str:
    return f"{resource_type.value}:{resource_id}"


class CapabilityRegistry:
    _default_instance: ClassVar["CapabilityRegistry" | None] = None

    def __init__(self) -> None:
        self._agent_capabilities: dict[AgentRole, AgentCapability] = {}
        self._model_capabilities: dict[tuple[str, str], ModelCapability] = {}
        self._capacities: dict[str, ExecutionCapacity] = {}
        self._capacity_index: dict[str, str] = {}
        self._active_allocations: dict[str, AllocationResult] = {}
        self._seed_defaults()

    @classmethod
    def default(cls) -> "CapabilityRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._agent_capabilities.clear()
        self._model_capabilities.clear()
        self._capacities.clear()
        self._capacity_index.clear()
        self._active_allocations.clear()
        self._seed_defaults()

    def register_agent_capability(self, capability: AgentCapability) -> AgentCapability:
        self._agent_capabilities[capability.role] = capability
        resource_id = capability.role.value
        capacity_key = _capacity_key(ResourceType.KILO_WORKER, resource_id)
        capacity_id = self._capacity_index.get(capacity_key)
        if capacity_id is None:
            self.register_capacity(
                ExecutionCapacity(
                    resource_type=ResourceType.KILO_WORKER,
                    resource_id=resource_id,
                    max_slots=capability.max_concurrent_tasks,
                    metadata={"kind": "agent_role_capacity", "role": capability.role.value},
                )
            )
        else:
            existing = self._capacities[capacity_id]
            self._capacities[capacity_id] = existing.model_copy(
                update={"max_slots": capability.max_concurrent_tasks}
            )
        return capability

    def register_model_capability(self, capability: ModelCapability) -> ModelCapability:
        key = self._model_key(capability.provider, capability.model)
        self._model_capabilities[key] = capability
        capacity_key = _capacity_key(
            ResourceType.MODEL,
            f"{capability.provider}:{capability.model}",
        )
        capacity_id = self._capacity_index.get(capacity_key)
        if capacity_id is None:
            self.register_capacity(
                ExecutionCapacity(
                    resource_type=ResourceType.MODEL,
                    resource_id=f"{capability.provider}:{capability.model}",
                    max_slots=capability.max_concurrent_requests,
                    metadata={
                        "kind": "model_capacity",
                        "provider": capability.provider,
                        "model": capability.model,
                        "estimated_cost_tier": capability.estimated_cost_tier,
                    },
                )
            )
        else:
            existing = self._capacities[capacity_id]
            self._capacities[capacity_id] = existing.model_copy(
                update={"max_slots": capability.max_concurrent_requests}
            )
        return capability

    def get_agent_capability(self, role: AgentRole) -> AgentCapability | None:
        return self._agent_capabilities.get(role)

    def get_model_capability(self, provider: str, model: str) -> ModelCapability | None:
        return self._model_capabilities.get(self._model_key(provider, model))

    def list_capabilities(self) -> dict[str, list[AgentCapability | ModelCapability]]:
        return {
            "agents": list(self._agent_capabilities.values()),
            "models": list(self._model_capabilities.values()),
        }

    def register_capacity(self, capacity: ExecutionCapacity) -> ExecutionCapacity:
        self._capacities[capacity.capacity_id] = capacity
        self._capacity_index[_capacity_key(capacity.resource_type, capacity.resource_id)] = (
            capacity.capacity_id
        )
        return capacity

    def list_capacity(self) -> list[ExecutionCapacity]:
        return sorted(self._capacities.values(), key=lambda item: item.capacity_id)

    def request_allocation(self, request: AllocationRequest) -> AllocationResult:
        agent_capability = self.get_agent_capability(request.role)
        model_capability = self.get_model_capability(request.provider, request.model)
        capacities, missing_capacities = self._resolve_request_capacities(request)
        status, reason = evaluate_allocation_request(
            request,
            agent_capability_exists=agent_capability is not None,
            model_capability_exists=model_capability is not None,
            mode_supported=(
                agent_capability is not None and request.mode in agent_capability.supported_modes
            ),
            capacities=capacities,
            missing_capacities=missing_capacities,
        )
        if status != AllocationStatus.GRANTED:
            return AllocationResult(
                status=status,
                granted=False,
                reason=reason,
                allocated_resources=[],
                metadata={
                    "request_id": request.request_id,
                    "project": request.project,
                    "issue_id": request.issue_id,
                    "task_id": request.task_id,
                    "capacity_ids": [],
                },
            )

        updated_capacities = []
        for capacity in capacities:
            updated = capacity.model_copy(update={"used_slots": capacity.used_slots + 1})
            self._capacities[capacity.capacity_id] = updated
            updated_capacities.append(updated)
        allocated_resources = [
            {
                "capacity_id": capacity.capacity_id,
                "resource_type": capacity.resource_type.value,
                "resource_id": capacity.resource_id,
                "used_slots": capacity.used_slots,
                "max_slots": capacity.max_slots,
            }
            for capacity in updated_capacities
        ]
        result = AllocationResult(
            status=AllocationStatus.GRANTED,
            granted=True,
            reason=reason,
            allocated_resources=allocated_resources,
            metadata={
                "request_id": request.request_id,
                "project": request.project,
                "issue_id": request.issue_id,
                "task_id": request.task_id,
                "capacity_ids": [capacity["capacity_id"] for capacity in allocated_resources],
            },
        )
        self._active_allocations[result.allocation_id] = result
        return result

    def release_allocation(self, allocation_id: str) -> AllocationResult | None:
        result = self._active_allocations.pop(allocation_id, None)
        if result is None or not result.granted:
            return result
        for resource in result.allocated_resources:
            capacity_id = str(resource.get("capacity_id"))
            capacity = self._capacities.get(capacity_id)
            if capacity is None:
                continue
            self._capacities[capacity.capacity_id] = capacity.model_copy(
                update={"used_slots": max(0, capacity.used_slots - 1)}
            )
        return result

    def list_active_allocations(self) -> list[AllocationResult]:
        return sorted(self._active_allocations.values(), key=lambda item: item.allocation_id)

    def _resolve_request_capacities(
        self,
        request: AllocationRequest,
    ) -> tuple[list[ExecutionCapacity], list[str]]:
        capacities: list[ExecutionCapacity] = []
        missing: list[str] = []
        required = [
            {
                "resource_type": ResourceType.KILO_WORKER.value,
                "resource_id": request.role.value,
            },
            {
                "resource_type": ResourceType.MODEL.value,
                "resource_id": f"{request.provider}:{request.model}",
            },
            *request.required_resources,
        ]
        seen_capacity_ids: set[str] = set()
        for resource in required:
            raw_type = resource.get("resource_type")
            raw_resource_id = resource.get("resource_id")
            if raw_type is None or raw_resource_id is None:
                continue
            resource_type = ResourceType(str(raw_type))
            resource_id = str(raw_resource_id)
            capacity_id = self._capacity_index.get(_capacity_key(resource_type, resource_id))
            if capacity_id is None:
                missing.append(f"{resource_type.value}:{resource_id}")
                continue
            if capacity_id in seen_capacity_ids:
                continue
            seen_capacity_ids.add(capacity_id)
            capacities.append(self._capacities[capacity_id])
        return capacities, missing

    def _seed_defaults(self) -> None:
        default_agent_capabilities = {
            AgentRole.PM: [KiloExecutionMode.ASK],
            AgentRole.PO: [KiloExecutionMode.PLAN],
            AgentRole.DEV: [KiloExecutionMode.CODE],
            AgentRole.QA: [KiloExecutionMode.DEBUG],
            AgentRole.QC: [KiloExecutionMode.ASK],
        }
        for role, supported_modes in default_agent_capabilities.items():
            self.register_agent_capability(
                AgentCapability(
                    role=role,
                    supported_modes=supported_modes,
                    max_concurrent_tasks=1,
                    supported_resource_types=[
                        ResourceType.KILO_WORKER,
                        ResourceType.MODEL,
                        ResourceType.WORKSPACE,
                    ],
                    default_priority=TaskPriority.NORMAL,
                    metadata={"seeded": True},
                )
            )
        for router_role in RouterAgentRole:
            resolution = resolve_model(RoutingRequest(role=router_role))
            self.register_model_capability(
                ModelCapability(
                    provider=resolution.provider.value,
                    model=resolution.model,
                    max_concurrent_requests=1,
                    estimated_cost_tier=_estimate_cost_tier(router_role),
                    supports_structured_output=True,
                    supports_long_context=router_role in {
                        RouterAgentRole.PM,
                        RouterAgentRole.PO,
                        RouterAgentRole.QC,
                    },
                    metadata={"seeded": True, "source": resolution.source, "role": router_role.value},
                )
            )

    @staticmethod
    def _model_key(provider: str, model: str) -> tuple[str, str]:
        return (provider.strip().upper(), model.strip())


def _estimate_cost_tier(role: RouterAgentRole) -> str:
    if role in {RouterAgentRole.PM, RouterAgentRole.PO, RouterAgentRole.QC}:
        return "HIGH"
    return "MEDIUM"
