from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from app.api.routes import evaluations as evaluations_routes
from app.core.config import load_settings
from app.core.model_execution import build_dry_run_model_executor
from lummevia_agents import PromptPipeline
from lummevia_core import AgentRole
from lummevia_datasets import get_dataset
from lummevia_evaluations import PromptBaselineRegistry, PromotionStatus
from lummevia_evaluations.regression import PromptRegressionRunner
from lummevia_integrations import PhoenixClient
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


def test_pm_regression_run_endpoint_returns_regression_result(monkeypatch) -> None:
    monkeypatch.setattr(
        evaluations_routes,
        "settings",
        load_settings({"DEEPSEEK_ENABLED": "false"}),
    )

    response = client.post(
        "/evaluations/pm/regression-run",
        json={"project": "lummevia-os"},
    )

    assert response.status_code == 200
    body = response.json()

    assert body["dataset_id"] == "pm_business_brief_dataset"
    assert body["template_id"] == "pm_business_brief"
    assert body["template_version"] == "v1"
    assert body["summary"]["total"] == 5
    assert body["summary"]["passed"] == 5
    assert body["summary"]["failed"] == 0
    assert body["summary"]["avg_score"] > 0
    assert len(body["cases"]) == 5
    assert all(case["passed"] is True for case in body["cases"])


def test_pm_regression_run_emits_phoenix_metadata(monkeypatch) -> None:
    exporter = RecordingSpanExporter()
    monkeypatch.setattr(
        evaluations_routes,
        "settings",
        load_settings(
            {
                "PHOENIX_ENABLED": "true",
                "PHOENIX_BASE_URL": "http://phoenix:6006",
                "DEEPSEEK_ENABLED": "false",
            }
        ),
    )
    monkeypatch.setattr(
        evaluations_routes,
        "_build_phoenix_client",
        lambda: PhoenixClient(span_exporter=exporter),
    )

    response = client.post(
        "/evaluations/pm/regression-run",
        json={"project": "lummevia-os"},
    )

    assert response.status_code == 200
    assert exporter.spans
    span = next(span for span in exporter.spans if span.name == "pm_regression_run")
    assert span.attributes["run_type"] == "pm_regression_run"
    assert span.attributes["dataset_id"] == "pm_business_brief_dataset"
    assert span.attributes["template_id"] == "pm_business_brief"
    assert span.attributes["project"] == "lummevia-os"
    assert span.attributes["total_cases"] == 5
    assert span.attributes["passed_cases"] == 5
    assert span.attributes["failed_cases"] == 0
    assert span.attributes["avg_score"] > 0
    assert span.attributes["avg_latency_ms"] >= 0
    assert span.attributes["regression_run_id"]


def test_pm_regression_run_fails_clearly_without_api_key_when_enabled(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        evaluations_routes,
        "settings",
        load_settings({"DEEPSEEK_ENABLED": "true"}),
    )

    response = client.post(
        "/evaluations/pm/regression-run",
        json={"project": "lummevia-os"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "DEEPSEEK_API_KEY is required when DEEPSEEK_ENABLED=true."
    }


def test_pm_promote_endpoint_registers_first_baseline(monkeypatch) -> None:
    baseline_registry = PromptBaselineRegistry()
    monkeypatch.setattr(
        evaluations_routes,
        "_get_baseline_registry",
        lambda: baseline_registry,
    )
    monkeypatch.setattr(
        evaluations_routes,
        "settings",
        load_settings({"DEEPSEEK_ENABLED": "false"}),
    )

    response = client.post(
        "/evaluations/pm/promote",
        json={
            "template_id": "pm_business_brief",
            "candidate_version": "v1",
            "promoted_by": "pm",
            "notes": "initial promotion",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["promotion"]["promotion_status"] == PromotionStatus.PROMOTED.value
    assert body["promotion"]["previous_version"] is None
    assert body["baseline_version"] is None
    assert body["candidate_version"] == "v1"
    assert body["regression_run"]["template_version"] == "v1"
    assert baseline_registry.get_active_version("pm_business_brief") == "v1"


def test_pm_promote_endpoint_emits_phoenix_metadata(monkeypatch) -> None:
    exporter = RecordingSpanExporter()
    baseline_registry = PromptBaselineRegistry()
    monkeypatch.setattr(
        evaluations_routes,
        "_get_baseline_registry",
        lambda: baseline_registry,
    )
    monkeypatch.setattr(
        evaluations_routes,
        "settings",
        load_settings(
            {
                "PHOENIX_ENABLED": "true",
                "PHOENIX_BASE_URL": "http://phoenix:6006",
                "DEEPSEEK_ENABLED": "false",
            }
        ),
    )
    monkeypatch.setattr(
        evaluations_routes,
        "_build_phoenix_client",
        lambda: PhoenixClient(span_exporter=exporter),
    )

    dataset = get_dataset("pm_business_brief_dataset")
    model_executor = build_dry_run_model_executor(
        AgentRole.PM,
        deepseek=evaluations_routes.settings.deepseek,
    )
    regression_run = PromptRegressionRunner(
        pipeline=PromptPipeline(model_executor=model_executor),
    ).run_dataset(dataset, project="lummevia-os", template_version="v1")
    baseline_registry.promote(
        template_id="pm_business_brief",
        candidate_version="v1",
        regression_run=regression_run,
    )

    response = client.post(
        "/evaluations/pm/promote",
        json={
            "template_id": "pm_business_brief",
            "candidate_version": "v1",
        },
    )

    assert response.status_code == 200
    span = next(span for span in exporter.spans if span.name == "pm_prompt_promotion")
    assert span.attributes["run_type"] == "pm_prompt_promotion"
    assert span.attributes["template_id"] == "pm_business_brief"
    assert span.attributes["baseline_version"] == "v1"
    assert span.attributes["candidate_version"] == "v1"
    assert span.attributes["promotion_status"] == PromotionStatus.PROMOTED.value
    assert span.attributes["regression_delta_score"] == 0.0
    assert "regression_delta_latency" in span.attributes
