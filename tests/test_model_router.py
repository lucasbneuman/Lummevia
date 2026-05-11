import pytest
from pydantic import ValidationError

from model_router import (
    AgentRole,
    ModelRouterError,
    Provider,
    RoutingRequest,
    UnknownRoleError,
    resolve_model,
)
from model_router import registry as registry_module


def test_resolve_pm_returns_default_config() -> None:
    resolution = resolve_model(RoutingRequest(role=AgentRole.PM))

    assert resolution.role == AgentRole.PM
    assert resolution.provider == Provider.DEEPSEEK
    assert resolution.model == "deepseek-v4-strong-placeholder"
    assert resolution.source == "default"


def test_resolve_dev_returns_default_config() -> None:
    resolution = resolve_model(RoutingRequest(role=AgentRole.DEV))

    assert resolution.role == AgentRole.DEV
    assert resolution.provider == Provider.DEEPSEEK
    assert resolution.model == "deepseek-v4-lite-placeholder"
    assert resolution.source == "default"


def test_resolve_uses_default_when_no_project_or_environment_override_exists() -> None:
    resolution = resolve_model(
        RoutingRequest(
            role=AgentRole.QA,
            project="unknown-project",
            environment="sandbox",
        )
    )

    assert resolution.role == AgentRole.QA
    assert resolution.source == "default"


def test_resolve_respects_project_environment_precedence() -> None:
    resolution = resolve_model(
        RoutingRequest(
            role=AgentRole.PM,
            project="lummevia-os",
            environment="production",
        )
    )

    assert resolution.model == "deepseek-v4-strong-placeholder"
    assert resolution.source == "project_environment"


def test_resolve_model_applies_environment_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_PM", "custom/pm-model")

    resolution = resolve_model(RoutingRequest(role=AgentRole.PM))

    assert resolution.model == "custom/pm-model"
    assert resolution.provider == Provider.DEEPSEEK
    assert resolution.source == "env_override"


def test_resolve_model_applies_complete_pm_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_PM_PROVIDER", "OPENAI")
    monkeypatch.setenv("MODEL_PM_NAME", "gpt-4.1-mini")
    monkeypatch.setenv("MODEL_PM_TEMPERATURE", "0.65")
    monkeypatch.setenv("MODEL_PM_MAX_TOKENS", "8192")

    resolution = resolve_model(RoutingRequest(role=AgentRole.PM))

    assert resolution.provider == Provider.OPENAI
    assert resolution.model == "gpt-4.1-mini"
    assert resolution.temperature == 0.65
    assert resolution.max_tokens == 8192
    assert resolution.source == "env_override"


def test_resolve_model_applies_partial_pm_name_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_PM_NAME", "custom/pm-name")

    resolution = resolve_model(RoutingRequest(role=AgentRole.PM))

    assert resolution.provider == Provider.DEEPSEEK
    assert resolution.model == "custom/pm-name"
    assert resolution.temperature == 0.1
    assert resolution.max_tokens == 4096
    assert resolution.source == "env_override"


def test_resolve_model_raises_clear_error_for_invalid_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_PM_PROVIDER", "INVALID")

    with pytest.raises(ModelRouterError, match="Invalid provider override for role 'PM'"):
        resolve_model(RoutingRequest(role=AgentRole.PM))


def test_resolve_model_raises_clear_error_for_invalid_temperature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_PM_TEMPERATURE", "not-a-float")

    with pytest.raises(
        ModelRouterError,
        match="Invalid temperature override for role 'PM'",
    ):
        resolve_model(RoutingRequest(role=AgentRole.PM))


def test_resolve_model_raises_clear_error_for_invalid_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_PM_MAX_TOKENS", "not-an-int")

    with pytest.raises(
        ModelRouterError,
        match="Invalid max_tokens override for role 'PM'",
    ):
        resolve_model(RoutingRequest(role=AgentRole.PM))


def test_resolve_model_preserves_legacy_model_dev_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_DEV", "legacy/dev-model")

    resolution = resolve_model(RoutingRequest(role=AgentRole.DEV))

    assert resolution.provider == Provider.DEEPSEEK
    assert resolution.model == "legacy/dev-model"
    assert resolution.temperature == 0.1
    assert resolution.max_tokens == 4096
    assert resolution.source == "env_override"


def test_resolve_model_raises_unknown_role_when_registry_has_no_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(registry_module.DEFAULT_ROLE_CONFIGS, AgentRole.QC, None)

    with pytest.raises(UnknownRoleError):
        resolve_model(RoutingRequest(role=AgentRole.QC))


def test_routing_request_rejects_invalid_role() -> None:
    with pytest.raises(ValidationError):
        RoutingRequest(role="INVALID")
