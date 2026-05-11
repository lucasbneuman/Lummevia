import os

from model_router.exceptions import InvalidEnvironmentOverrideError
from model_router.registry import get_model_config
from model_router.schemas import AgentRole, ModelConfig, Provider, RoutingRequest, RoutingResolution


def _get_env_value(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None

    stripped = value.strip()
    return stripped or None


def _parse_provider_override(role: AgentRole, raw_value: str) -> Provider:
    try:
        return Provider[raw_value.strip().upper()]
    except KeyError as exc:
        raise InvalidEnvironmentOverrideError(
            f"Invalid provider override for role '{role.value}': '{raw_value}'. "
            f"Expected one of: {', '.join(provider.value for provider in Provider)}."
        ) from exc


def _parse_temperature_override(role: AgentRole, raw_value: str) -> float:
    try:
        return float(raw_value)
    except ValueError as exc:
        raise InvalidEnvironmentOverrideError(
            f"Invalid temperature override for role '{role.value}': '{raw_value}'. "
            "Expected a float value."
        ) from exc


def _parse_max_tokens_override(role: AgentRole, raw_value: str) -> int:
    try:
        return int(raw_value)
    except ValueError as exc:
        raise InvalidEnvironmentOverrideError(
            f"Invalid max_tokens override for role '{role.value}': '{raw_value}'. "
            "Expected an integer value."
        ) from exc


def _apply_environment_overrides(role: AgentRole, config: ModelConfig) -> tuple[ModelConfig, str]:
    prefix = f"MODEL_{role.value}"
    provider_override = _get_env_value(f"{prefix}_PROVIDER")
    model_name_override = _get_env_value(f"{prefix}_NAME")
    temperature_override = _get_env_value(f"{prefix}_TEMPERATURE")
    max_tokens_override = _get_env_value(f"{prefix}_MAX_TOKENS")
    legacy_model_override = _get_env_value(prefix) if role in {AgentRole.PM, AgentRole.DEV} else None

    updates: dict[str, object] = {}

    if provider_override is not None:
        updates["provider"] = _parse_provider_override(role, provider_override)

    if model_name_override is not None:
        if (
            legacy_model_override is not None
            and model_name_override == config.model
            and legacy_model_override != config.model
        ):
            updates["model"] = legacy_model_override
        else:
            updates["model"] = model_name_override
    elif legacy_model_override is not None:
        updates["model"] = legacy_model_override

    if temperature_override is not None:
        updates["temperature"] = _parse_temperature_override(role, temperature_override)

    if max_tokens_override is not None:
        updates["max_tokens"] = _parse_max_tokens_override(role, max_tokens_override)

    if not updates:
        return config, "registry"

    overridden_config = config.model_copy(update=updates)

    if overridden_config == config:
        return config, "registry"

    return overridden_config, "env_override"


def resolve_model(request: RoutingRequest) -> RoutingResolution:
    config, source = get_model_config(
        role=request.role,
        project=request.project,
        environment=request.environment,
    )
    overridden_config, override_source = _apply_environment_overrides(request.role, config)

    return RoutingResolution(
        role=request.role,
        project=request.project,
        environment=request.environment,
        provider=overridden_config.provider,
        model=overridden_config.model,
        temperature=overridden_config.temperature,
        max_tokens=overridden_config.max_tokens,
        source=override_source if override_source == "env_override" else source,
    )
