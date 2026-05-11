from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from app.api.routes import evaluations as evaluations_routes
from app.core.config import load_settings
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
