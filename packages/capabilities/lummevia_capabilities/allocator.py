from __future__ import annotations

from typing import ClassVar

from lummevia_capabilities.registry import CapabilityRegistry
from lummevia_capabilities.schemas import AllocationRequest, AllocationResult


class CapabilityAllocator:
    _default_instance: ClassVar["CapabilityAllocator" | None] = None

    def __init__(self, registry: CapabilityRegistry | None = None) -> None:
        self.registry = registry or CapabilityRegistry.default()

    @classmethod
    def default(cls) -> "CapabilityAllocator":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def request_allocation(self, request: AllocationRequest) -> AllocationResult:
        return self.registry.request_allocation(request)

    def release_allocation(self, allocation_id: str) -> AllocationResult | None:
        return self.registry.release_allocation(allocation_id)
