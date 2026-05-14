from collections.abc import Sequence

from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from lummevia_evaluations import EvaluationStatus, PromptEvaluation, PromptEvaluationRegistry
from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_runtime import DevelopmentRuntime


class RecordingSpanExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans = []

    def export(self, spans: Sequence[object]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def test_phoenix_receives_learning_metadata() -> None:
    PromptEvaluationRegistry.default().register(
        PromptEvaluation(
            evaluation_id="eval-phoenix-learning",
            template_id="pm_business_brief",
            template_version="v1",
            provider="FAKE",
            model="fake:model",
            score=0.5,
            status=EvaluationStatus.NEEDS_REVIEW,
            metadata={"project": "lummevia-os"},
        )
    )
    exporter = RecordingSpanExporter()
    observer = PhoenixRuntimeObserver(
        PhoenixClient(span_exporter=exporter),
        environment="test",
    )
    runtime = DevelopmentRuntime(observer=observer)

    state = runtime.start_run(project="lummevia-os", issue_id="OS-PHX-LEARN")

    workflow_span = next(
        span for span in exporter.spans if span.name == "workflow_run:development_loop"
    )

    assert state.metadata["learning_signal_count"] >= 1
    assert workflow_span.attributes["learning_signal_count"] >= 1
    assert workflow_span.attributes["insight_count"] >= 1
    assert workflow_span.attributes["recommendation_count"] >= 1
    assert workflow_span.attributes["learning_severity"] in {"MEDIUM", "HIGH", "CRITICAL"}
    assert workflow_span.attributes["recommendation_type"]
