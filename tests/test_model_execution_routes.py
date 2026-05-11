from fastapi.testclient import TestClient

from app.api.routes import model_execution as model_execution_routes
from app.core.config import load_settings
from app.core.model_execution import build_dry_run_model_executor
from lummevia_agents import ModelExecutionRequest
from lummevia_core import AgentRole
from main import app


client = TestClient(app)


def test_pm_dry_run_endpoint_uses_fake_provider_when_deepseek_is_disabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        model_execution_routes,
        "settings",
        load_settings({"DEEPSEEK_ENABLED": "false"}),
    )

    response = client.post(
        "/model-execution/pm/dry-run",
        json={
            "project": "lummevia-os",
            "issue_id": "OS-1",
            "prompt": "Founder wants a safer PM dry-run.",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["provider"] == "FAKE"
    assert body["model"] == "fake:pm"
    assert body["fallback_used"] is True
    assert body["structured_output"]["issue_id"] == "OS-1"
    assert body["structured_output"]["business_brief_status"] == "draft"
    assert body["metadata"]["provider_adapter"] == "fake"
    assert body["metadata"]["model_raw_output"]["provider_adapter"] == "fake"


def test_pm_dry_run_endpoint_fails_clearly_without_api_key_when_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        model_execution_routes,
        "settings",
        load_settings({"DEEPSEEK_ENABLED": "true"}),
    )

    response = client.post(
        "/model-execution/pm/dry-run",
        json={
            "project": "lummevia-os",
            "issue_id": "OS-2",
            "prompt": "Founder wants DeepSeek enabled.",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "DEEPSEEK_API_KEY is required when DEEPSEEK_ENABLED=true."
    }


def test_non_pm_roles_stay_on_fake_provider_for_controlled_execution() -> None:
    settings = load_settings(
        {
            "DEEPSEEK_ENABLED": "true",
            "DEEPSEEK_API_KEY": "ds-key",
        }
    )

    for role in (AgentRole.PO, AgentRole.DEV, AgentRole.QA, AgentRole.QC):
        executor = build_dry_run_model_executor(role, deepseek=settings.deepseek)
        result = executor.execute(
            ModelExecutionRequest(
                role=role,
                project="lummevia-os",
                environment="development",
                prompt=f"Exercise {role.value} controlled execution",
                system_prompt=f"You are the {role.value} role in Lummevia OS.",
            )
        )

        assert result.provider == "FAKE"
        assert result.fallback_used is True
        assert result.metadata["fallback_reason"] == "real_provider_not_enabled_for_role"
