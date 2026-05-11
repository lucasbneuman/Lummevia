from __future__ import annotations

from lummevia_core import AgentRole

from app.core.config import OpenRouterSettings
from lummevia_agents import FakeModelProvider, ModelExecutor, OpenRouterModelProvider


def build_dry_run_model_executor(
    role: AgentRole,
    *,
    openrouter: OpenRouterSettings,
) -> ModelExecutor:
    if role is not AgentRole.PM:
        return ModelExecutor(
            provider=FakeModelProvider(
                fallback_used=True,
                fallback_reason="real_provider_not_enabled_for_role",
            )
        )

    if not openrouter.enabled:
        return ModelExecutor(
            provider=FakeModelProvider(
                fallback_used=True,
                fallback_reason="openrouter_disabled",
            )
        )

    if openrouter.api_key is None:
        raise ValueError(
            "OPENROUTER_API_KEY is required when OPENROUTER_ENABLED=true."
        )

    return ModelExecutor(
        provider=OpenRouterModelProvider(
            api_key=openrouter.api_key,
            base_url=openrouter.base_url,
            timeout_seconds=openrouter.timeout_seconds,
        )
    )
