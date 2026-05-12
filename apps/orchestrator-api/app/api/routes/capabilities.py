from fastapi import APIRouter

from lummevia_capabilities import AllocationResult, CapabilityRegistry
from lummevia_capabilities.schemas import AgentCapability, ExecutionCapacity, ModelCapability


router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("/agents", response_model=list[AgentCapability])
def list_agent_capabilities() -> list[AgentCapability]:
    return CapabilityRegistry.default().list_capabilities()["agents"]


@router.get("/models", response_model=list[ModelCapability])
def list_model_capabilities() -> list[ModelCapability]:
    return CapabilityRegistry.default().list_capabilities()["models"]


@router.get("/capacity", response_model=list[ExecutionCapacity])
def list_capacity() -> list[ExecutionCapacity]:
    return CapabilityRegistry.default().list_capacity()


@router.get("/allocations", response_model=list[AllocationResult])
def list_active_allocations() -> list[AllocationResult]:
    return CapabilityRegistry.default().list_active_allocations()
