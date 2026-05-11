from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from app.api.routes import model_execution as model_execution_routes
from app.core.config import load_settings
from app.core.model_execution import build_dry_run_model_executor
from lummevia_integrations import PhoenixClient
from lummevia_agents import ModelExecutionRequest
from lummevia_core import AgentRole
from main import app


client = TestClient(app)


class RecordingSpanExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans = []

    def export(self, spans) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


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
    assert body["resolved_provider"] == "DEEPSEEK"
    assert body["resolved_model"] == "deepseek-chat"
    assert body["effective_provider"] == "FAKE"
    assert body["effective_model"] == "fake:pm"
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


def test_pm_dry_run_emits_phoenix_metadata_without_sensitive_prompt_or_keys(
    monkeypatch,
    caplog,
) -> None:
    exporter = RecordingSpanExporter()
    monkeypatch.setattr(
        model_execution_routes,
        "settings",
        load_settings(
            {
                "PHOENIX_ENABLED": "true",
                "PHOENIX_BASE_URL": "http://phoenix:6006",
                "DEEPSEEK_ENABLED": "false",
                "DEEPSEEK_API_KEY": "ds-secret-key",
            }
        ),
    )
    monkeypatch.setattr(
        model_execution_routes,
        "_build_phoenix_client",
        lambda: PhoenixClient(span_exporter=exporter),
    )

    response = client.post(
        "/model-execution/pm/dry-run",
        json={
            "project": "lummevia-os",
            "issue_id": "OS-3",
            "prompt": "Founder wants safer PM observability.",
        },
    )

    assert response.status_code == 200
    assert exporter.spans
    span = next(span for span in exporter.spans if span.name == "pm_dry_run")
    assert span.attributes["run_type"] == "pm_dry_run"
    assert span.attributes["project"] == "lummevia-os"
    assert span.attributes["issue_id"] == "OS-3"
    assert span.attributes["resolved_provider"] == "DEEPSEEK"
    assert span.attributes["resolved_model"] == "deepseek-chat"
    assert span.attributes["effective_provider"] == "FAKE"
    assert span.attributes["effective_model"] == "fake:pm"
    assert span.attributes["status"] == "completed"
    assert span.attributes["fallback_used"] is True
    assert "prompt" not in span.attributes
    assert "ds-secret-key" not in caplog.text
