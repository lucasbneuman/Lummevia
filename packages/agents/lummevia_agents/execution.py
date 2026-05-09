from __future__ import annotations

from time import perf_counter
from typing import Any, Protocol

from pydantic import Field

from lummevia_core import AgentRole
from model_router import AgentRole as RouterAgentRole
from model_router import RoutingRequest, RoutingResolution, resolve_model

from lummevia_agents.exceptions import AgentError
from lummevia_agents.schemas import AgentBaseSchema


class ModelExecutionRequest(AgentBaseSchema):
    role: AgentRole
    project: str | None = None
    environment: str | None = None
    prompt: str = Field(min_length=1)
    system_prompt: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelExecutionResult(AgentBaseSchema):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    output: str = Field(min_length=1)
    raw_output: Any = None
    latency_ms: int = Field(ge=0)
    fallback_used: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelExecutionError(AgentError):
    """Raised when model execution cannot complete successfully."""

    def __init__(
        self,
        message: str,
        *,
        role: AgentRole | None = None,
        project: str | None = None,
        environment: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        super().__init__(message)
        self.role = role
        self.project = project
        self.environment = environment
        self.provider = provider
        self.model = model


class ProviderExecutionPayload(AgentBaseSchema):
    output: str = Field(min_length=1)
    raw_output: Any = None
    fallback_used: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelProvider(Protocol):
    def execute(
        self,
        request: ModelExecutionRequest,
        resolution: RoutingResolution,
    ) -> ProviderExecutionPayload: ...


class FakeModelProvider:
    """Deterministic provider used to exercise model execution flows in tests."""

    def __init__(self, *, fail_for_prompts: set[str] | None = None) -> None:
        self.fail_for_prompts = fail_for_prompts or set()

    def execute(
        self,
        request: ModelExecutionRequest,
        resolution: RoutingResolution,
    ) -> ProviderExecutionPayload:
        if request.prompt in self.fail_for_prompts:
            raise RuntimeError(
                "Fake provider was configured to fail for the supplied prompt."
            )

        system_prompt = request.system_prompt or "NO_SYSTEM_PROMPT"
        scope = f"{request.project or 'NO_PROJECT'}|{request.environment or 'NO_ENV'}"
        output = (
            f"[fake:{request.role.value.lower()}]"
            f" scope={scope}"
            f" model={resolution.model}"
            f" system={system_prompt}"
            f" prompt={request.prompt}"
        )

        return ProviderExecutionPayload(
            output=output,
            raw_output={
                "provider_adapter": "fake",
                "resolved_provider": resolution.provider.value,
                "resolved_model": resolution.model,
                "prompt": request.prompt,
                "system_prompt": request.system_prompt,
                "role": request.role.value,
            },
            metadata={
                "provider_adapter": "fake",
                "routing_source": resolution.source,
            },
        )


class ModelExecutor:
    def __init__(self, provider: ModelProvider | None = None) -> None:
        self.provider = provider or FakeModelProvider()

    def execute(self, request: ModelExecutionRequest) -> ModelExecutionResult:
        resolution = resolve_model(
            RoutingRequest(
                role=RouterAgentRole[request.role.value],
                project=request.project,
                environment=request.environment,
            )
        )

        started_at = perf_counter()

        try:
            payload = self.provider.execute(request, resolution)
        except Exception as exc:
            raise ModelExecutionError(
                "Model provider execution failed "
                f"for role '{request.role.value}' using provider "
                f"'{resolution.provider.value}' and model '{resolution.model}'.",
                role=request.role,
                project=request.project,
                environment=request.environment,
                provider=resolution.provider.value,
                model=resolution.model,
            ) from exc

        latency_ms = int((perf_counter() - started_at) * 1000)
        metadata = dict(request.metadata)
        metadata.update(payload.metadata)
        metadata.update(
            {
                "role": request.role.value,
                "project": request.project,
                "environment": request.environment,
                "provider": resolution.provider.value,
                "model": resolution.model,
                "latency_ms": latency_ms,
                "fallback_used": payload.fallback_used,
            }
        )

        return ModelExecutionResult(
            provider=resolution.provider.value,
            model=resolution.model,
            output=payload.output,
            raw_output=payload.raw_output,
            latency_ms=latency_ms,
            fallback_used=payload.fallback_used,
            metadata=metadata,
        )
