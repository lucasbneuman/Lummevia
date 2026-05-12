from __future__ import annotations

from lummevia_core import AgentRole

from app.core.config import DeepSeekSettings
from lummevia_agents import DeepSeekModelProvider, FakeModelProvider, ModelExecutor


def build_dry_run_model_executor(
    role: AgentRole,
    *,
    deepseek: DeepSeekSettings,
) -> ModelExecutor:
    if role is not AgentRole.PM:
        return ModelExecutor(
            provider=FakeModelProvider(
                fallback_used=True,
                fallback_reason="real_provider_not_enabled_for_role",
            )
        )

    if not deepseek.enabled:
        return ModelExecutor(
            provider=FakeModelProvider(
                fallback_used=True,
                fallback_reason="deepseek_disabled",
            )
        )

    if deepseek.api_key is None:
        raise ValueError(
            "DEEPSEEK_API_KEY is required when DEEPSEEK_ENABLED=true."
        )

    return ModelExecutor(
        provider=DeepSeekModelProvider(
            api_key=deepseek.api_key,
            base_url=deepseek.base_url,
            timeout_seconds=deepseek.timeout_seconds,
        )
    )


def build_pm_conversation_model_executor(*, deepseek: DeepSeekSettings) -> ModelExecutor:
    return build_dry_run_model_executor(AgentRole.PM, deepseek=deepseek)
