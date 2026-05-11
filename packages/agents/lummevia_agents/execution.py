from __future__ import annotations

from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Any, Protocol

import httpx
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
    resolved_provider: str = Field(min_length=1)
    resolved_model: str = Field(min_length=1)
    effective_provider: str = Field(min_length=1)
    effective_model: str = Field(min_length=1)
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
    provider: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelProvider(Protocol):
    def execute(
        self,
        request: ModelExecutionRequest,
        resolution: RoutingResolution,
    ) -> ProviderExecutionPayload: ...


class FakeModelProvider:
    """Deterministic provider used to exercise model execution flows in tests."""

    def __init__(
        self,
        *,
        fail_for_prompts: set[str] | None = None,
        fallback_used: bool = False,
        fallback_reason: str | None = None,
    ) -> None:
        self.fail_for_prompts = fail_for_prompts or set()
        self.fallback_used = fallback_used
        self.fallback_reason = fallback_reason

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
            fallback_used=self.fallback_used,
            provider="FAKE",
            model=f"fake:{request.role.value.lower()}",
            metadata={
                "provider_adapter": "fake",
                "routing_source": resolution.source,
                "effective_provider": "FAKE",
                "effective_model": f"fake:{request.role.value.lower()}",
                "provider_reported_model": f"fake:{request.role.value.lower()}",
                "fallback_reason": self.fallback_reason,
            },
        )


class DeepSeekModelProvider:
    """Real provider for direct DeepSeek chat completions."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: int = 60,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client

    def execute(
        self,
        request: ModelExecutionRequest,
        resolution: RoutingResolution,
    ) -> ProviderExecutionPayload:
        payload = {
            "model": resolution.model,
            "messages": self._build_messages(request),
            "temperature": resolution.temperature,
            "max_tokens": resolution.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        endpoint = f"{self.base_url}/chat/completions"

        try:
            if self.http_client is not None:
                response = self.http_client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
            else:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        endpoint,
                        json=payload,
                        headers=headers,
                    )
        except httpx.TimeoutException as exc:
            raise RuntimeError(
                "DeepSeek request timed out after "
                f"{self.timeout_seconds} seconds."
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"DeepSeek request failed: {exc}.") from exc

        if response.status_code >= 400:
            raise RuntimeError(
                "DeepSeek request failed with status "
                f"{response.status_code}: {self._extract_error_message(response)}"
            )

        response_payload = response.json()
        output = self._extract_output_text(response_payload)
        provider_name = resolution.provider.value
        model_name = str(response_payload.get("model") or resolution.model)
        usage = response_payload.get("usage")

        metadata: dict[str, Any] = {
            "provider_adapter": "deepseek",
            "routing_source": resolution.source,
            "effective_provider": provider_name,
            "effective_model": model_name,
            "provider_reported_model": model_name,
        }
        if usage is not None:
            metadata["usage"] = usage

        return ProviderExecutionPayload(
            output=output,
            raw_output=response_payload,
            provider=provider_name,
            model=model_name,
            metadata=metadata,
        )

    def _build_messages(self, request: ModelExecutionRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        return messages

    def _extract_error_message(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text or "Unknown DeepSeek error."

        error = payload.get("error")
        if isinstance(error, Mapping):
            message = error.get("message")
            if message:
                return str(message)

        detail = payload.get("detail")
        if detail:
            return str(detail)

        return response.text or "Unknown DeepSeek error."

    def _extract_output_text(self, payload: Mapping[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, Sequence) or not choices:
            raise RuntimeError("DeepSeek response did not include any choices.")

        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            raise RuntimeError("DeepSeek response choice had an invalid shape.")

        message = first_choice.get("message")
        if not isinstance(message, Mapping):
            raise RuntimeError("DeepSeek response did not include a message payload.")

        content = message.get("content")
        if isinstance(content, str):
            stripped = content.strip()
            if stripped:
                return stripped
        elif isinstance(content, Sequence):
            text_parts: list[str] = []
            for item in content:
                if not isinstance(item, Mapping):
                    continue
                if item.get("type") == "text" and item.get("text"):
                    text_parts.append(str(item["text"]))
            joined = "".join(text_parts).strip()
            if joined:
                return joined

        raise RuntimeError("DeepSeek response did not include textual content.")


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
        effective_provider = payload.provider or resolution.provider.value
        effective_model = payload.model or resolution.model
        metadata = dict(request.metadata)
        metadata.update(payload.metadata)
        metadata.update(
            {
                "role": request.role.value,
                "project": request.project,
                "environment": request.environment,
                "provider": effective_provider,
                "model": effective_model,
                "resolved_provider": resolution.provider.value,
                "resolved_model": resolution.model,
                "effective_provider": effective_provider,
                "effective_model": effective_model,
                "latency_ms": latency_ms,
                "fallback_used": payload.fallback_used,
            }
        )

        return ModelExecutionResult(
            provider=effective_provider,
            model=effective_model,
            resolved_provider=resolution.provider.value,
            resolved_model=resolution.model,
            effective_provider=effective_provider,
            effective_model=effective_model,
            output=payload.output,
            raw_output=payload.raw_output,
            latency_ms=latency_ms,
            fallback_used=payload.fallback_used,
            metadata=metadata,
        )
