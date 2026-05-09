from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from main import app
from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_runtime import DevelopmentRuntime, RuntimeState
from lummevia_runtime.observability import RuntimeObserver


class RecordingSpanExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans = []

    def export(self, spans: Sequence[object]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


class FailingObserver(RuntimeObserver):
    @contextmanager
    def observe_workflow_run(self, state: RuntimeState) -> Iterator[None]:
        raise RuntimeError("phoenix workflow span failed")
        yield

    @contextmanager
    def observe_step(self, state: RuntimeState, step_name: str) -> Iterator[None]:
        raise RuntimeError("phoenix step span failed")
        yield

    def record_runtime_error(
        self,
        state: RuntimeState,
        error: Exception,
        *,
        step_name: str | None = None,
    ) -> None:
        raise RuntimeError("phoenix runtime error reporting failed")


def test_runtime_completes_when_phoenix_is_disabled() -> None:
    observer = PhoenixRuntimeObserver(
        PhoenixClient(enabled=False),
        environment="test",
    )
    runtime = DevelopmentRuntime(observer=observer)

    state = runtime.start_run(project="lummevia-os", issue_id="OS-201")

    assert state.run.run_id.startswith("run-")
    assert state.run.project == "lummevia-os"
    assert state.run.issue_id == "OS-201"
    assert state.run.status.value == "COMPLETED"


def test_runtime_completes_when_phoenix_observer_fails() -> None:
    runtime = DevelopmentRuntime(observer=FailingObserver())

    state = runtime.start_run(project="lummevia-os", issue_id="OS-202")

    assert state.run.run_id.startswith("run-")
    assert state.run.status.value == "COMPLETED"
    assert state.artifacts.final_validation is not None


def test_phoenix_runtime_observer_exports_run_metadata() -> None:
    exporter = RecordingSpanExporter()
    observer = PhoenixRuntimeObserver(
        PhoenixClient(span_exporter=exporter),
        environment="test",
    )
    runtime = DevelopmentRuntime(observer=observer)

    state = runtime.start_run(project="lummevia-os", issue_id="OS-203")

    assert state.run.status.value == "COMPLETED"
    assert exporter.spans

    workflow_span = next(
        span for span in exporter.spans if span.name == "workflow_run:development_loop"
    )
    assert workflow_span.attributes["run_id"] == state.run.run_id
    assert workflow_span.attributes["project"] == "lummevia-os"
    assert workflow_span.attributes["issue_id"] == "OS-203"
    assert workflow_span.attributes["workflow"] == "development_loop"
    assert workflow_span.attributes["environment"] == "test"
    assert workflow_span.attributes["status"] == "COMPLETED"

    step_names = {span.name for span in exporter.spans}
    assert "step:dev_implementation" in step_names
    assert "step:qa_validation" in step_names
    assert "step:dev_qa_iteration" in step_names


def test_runtime_route_returns_workflow_run_when_phoenix_fails(monkeypatch) -> None:
    from app.api.routes import runtime as runtime_routes

    client = TestClient(app)
    monkeypatch.setattr(
        runtime_routes,
        "runtime_service",
        DevelopmentRuntime(observer=FailingObserver()),
    )

    response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-204"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["run"]["run_id"].startswith("run-")
    assert body["run"]["project"] == "lummevia-os"
    assert body["run"]["issue_id"] == "OS-204"
    assert body["run"]["status"] == "COMPLETED"
