from fastapi.testclient import TestClient

from lummevia_capabilities import (
    AgentCapability,
    AllocationRequest,
    AllocationStatus,
    CapabilityAllocator,
    CapabilityRegistry,
    ExecutionCapacity,
    ModelCapability,
)
from lummevia_core import AgentRole
from lummevia_kilo import KiloExecutionMode
from lummevia_queue import TaskPriority
from lummevia_resources import ResourceType
from main import app


client = TestClient(app)


def test_register_and_get_agent_capability() -> None:
    registry = CapabilityRegistry()
    capability = AgentCapability(
        role=AgentRole.DEV,
        supported_modes=[KiloExecutionMode.CODE],
        max_concurrent_tasks=2,
        supported_resource_types=[ResourceType.KILO_WORKER, ResourceType.MODEL],
        default_priority=TaskPriority.HIGH,
        metadata={"source": "test"},
    )

    registry.register_agent_capability(capability)
    stored = registry.get_agent_capability(AgentRole.DEV)

    assert stored is not None
    assert stored.role == AgentRole.DEV
    assert stored.max_concurrent_tasks == 2
    assert stored.default_priority == TaskPriority.HIGH
    assert stored.metadata["source"] == "test"


def test_register_and_get_model_capability() -> None:
    registry = CapabilityRegistry()
    capability = ModelCapability(
        provider="OPENAI",
        model="gpt-test",
        max_concurrent_requests=2,
        estimated_cost_tier="MEDIUM",
        supports_structured_output=True,
        supports_long_context=True,
        metadata={"source": "test"},
    )

    registry.register_model_capability(capability)
    stored = registry.get_model_capability("OPENAI", "gpt-test")

    assert stored is not None
    assert stored.provider == "OPENAI"
    assert stored.model == "gpt-test"
    assert stored.max_concurrent_requests == 2
    assert stored.supports_long_context is True


def test_allocation_is_granted_when_slots_are_available() -> None:
    registry = CapabilityRegistry()
    result = registry.request_allocation(
        AllocationRequest(
            request_id="req-1",
            project="lummevia-os",
            issue_id="OS-1000",
            task_id="OS-1000-T1",
            role=AgentRole.DEV,
            mode=KiloExecutionMode.CODE,
            provider="DEEPSEEK",
            model="deepseek-v4-lite-placeholder",
            priority=TaskPriority.NORMAL,
        )
    )

    assert result.status == AllocationStatus.GRANTED
    assert result.granted is True
    assert len(result.allocated_resources) == 2
    assert registry.list_active_allocations()


def test_allocation_waits_when_slots_are_exhausted() -> None:
    registry = CapabilityRegistry()
    registry.register_capacity(
        ExecutionCapacity(
            resource_type=ResourceType.KILO_WORKER,
            resource_id="custom-dev",
            max_slots=1,
            metadata={"source": "test"},
        )
    )
    first = registry.request_allocation(
        AllocationRequest(
            request_id="req-2a",
            project="lummevia-os",
            issue_id="OS-1001",
            task_id="OS-1001-T1",
            role=AgentRole.DEV,
            mode=KiloExecutionMode.CODE,
            provider="DEEPSEEK",
            model="deepseek-v4-lite-placeholder",
            required_resources=[
                {
                    "resource_type": ResourceType.KILO_WORKER.value,
                    "resource_id": "custom-dev",
                }
            ],
        )
    )
    second = registry.request_allocation(
        AllocationRequest(
            request_id="req-2b",
            project="lummevia-os",
            issue_id="OS-1001",
            task_id="OS-1001-T2",
            role=AgentRole.DEV,
            mode=KiloExecutionMode.CODE,
            provider="DEEPSEEK",
            model="deepseek-v4-lite-placeholder",
            required_resources=[
                {
                    "resource_type": ResourceType.KILO_WORKER.value,
                    "resource_id": "custom-dev",
                }
            ],
        )
    )

    assert first.status == AllocationStatus.GRANTED
    assert second.status == AllocationStatus.WAITING
    assert second.granted is False


def test_allocation_is_denied_for_unsupported_mode() -> None:
    registry = CapabilityRegistry()
    result = registry.request_allocation(
        AllocationRequest(
            request_id="req-3",
            project="lummevia-os",
            issue_id="OS-1002",
            task_id="OS-1002-T1",
            role=AgentRole.DEV,
            mode=KiloExecutionMode.DEBUG,
            provider="DEEPSEEK",
            model="deepseek-v4-lite-placeholder",
        )
    )

    assert result.status == AllocationStatus.DENIED
    assert "not supported" in str(result.reason)


def test_release_allocation_frees_slot() -> None:
    registry = CapabilityRegistry()
    first = registry.request_allocation(
        AllocationRequest(
            request_id="req-4a",
            project="lummevia-os",
            issue_id="OS-1003",
            task_id="OS-1003-T1",
            role=AgentRole.DEV,
            mode=KiloExecutionMode.CODE,
            provider="DEEPSEEK",
            model="deepseek-v4-lite-placeholder",
        )
    )
    assert first.status == AllocationStatus.GRANTED

    registry.release_allocation(first.allocation_id)

    second = registry.request_allocation(
        AllocationRequest(
            request_id="req-4b",
            project="lummevia-os",
            issue_id="OS-1003",
            task_id="OS-1003-T2",
            role=AgentRole.DEV,
            mode=KiloExecutionMode.CODE,
            provider="DEEPSEEK",
            model="deepseek-v4-lite-placeholder",
        )
    )

    assert second.status == AllocationStatus.GRANTED


def test_capability_endpoints_list_agents_models_capacity_and_allocations() -> None:
    allocation = CapabilityAllocator.default().request_allocation(
        AllocationRequest(
            request_id="req-endpoints",
            project="lummevia-os",
            issue_id="OS-1004",
            task_id="OS-1004-T1",
            role=AgentRole.DEV,
            mode=KiloExecutionMode.CODE,
            provider="DEEPSEEK",
            model="deepseek-v4-lite-placeholder",
        )
    )

    agents_response = client.get("/capabilities/agents")
    models_response = client.get("/capabilities/models")
    capacity_response = client.get("/capabilities/capacity")
    allocations_response = client.get("/capabilities/allocations")

    assert agents_response.status_code == 200
    assert models_response.status_code == 200
    assert capacity_response.status_code == 200
    assert allocations_response.status_code == 200
    assert any(item["role"] == "DEV" for item in agents_response.json())
    assert any(item["provider"] == "DEEPSEEK" for item in models_response.json())
    assert any(item["resource_type"] == "KILO_WORKER" for item in capacity_response.json())
    assert any(item["allocation_id"] == allocation.allocation_id for item in allocations_response.json())
