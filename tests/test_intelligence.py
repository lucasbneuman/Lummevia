from __future__ import annotations

from collections.abc import Sequence

from opentelemetry.sdk.trace.export import SpanExportResult, SpanExporter

from lummevia_intelligence import (
    AutonomyLevel,
    DecisionRegistry,
    DecisionStatus,
    DecisionType,
    ExecutionContext,
    evaluate_execution,
)
from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_reviews import HumanReviewRegistry, ReviewType
from lummevia_runtime import DevelopmentRuntime
from lummevia_timeline import build_workflow_timeline


class RecordingSpanExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans = []

    def export(self, spans: Sequence[object]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def test_qa_failed_proposes_retry_before_escalation() -> None:
    decision = evaluate_execution(
        ExecutionContext(
            workflow_run_id="run-qa-retry",
            task_id="OS-INT-T1",
            qa_status="FAILED",
            retry_count=0,
            max_retries=2,
            real_code_touched=True,
        )
    )

    assert decision.decision_type == DecisionType.RETRY
    assert decision.recommended_action == "RETRY"


def test_qa_failed_after_retry_proposes_escalate_review() -> None:
    decision = evaluate_execution(
        ExecutionContext(
            workflow_run_id="run-qa-escalate",
            task_id="OS-INT-T2",
            qa_status="FAILED",
            retry_count=1,
            max_retries=2,
            real_code_touched=True,
        )
    )

    assert decision.decision_type == DecisionType.ESCALATE_REVIEW
    assert decision.requires_human_review is True


def test_max_retries_proposes_stop() -> None:
    decision = evaluate_execution(
        ExecutionContext(
            workflow_run_id="run-stop",
            retry_count=2,
            max_retries=2,
            kilo_failed=True,
        )
    )

    assert decision.decision_type == DecisionType.STOP
    assert decision.recommended_action == "CANCEL"


def test_high_files_changed_proposes_escalate_review() -> None:
    decision = evaluate_execution(
        ExecutionContext(
            workflow_run_id="run-files",
            files_changed_count=12,
            real_code_touched=True,
        )
    )

    assert decision.decision_type == DecisionType.ESCALATE_REVIEW


def test_missing_context_proposes_request_more_context() -> None:
    decision = evaluate_execution(
        ExecutionContext(
            workflow_run_id="run-context",
            missing_context=True,
        )
    )

    assert decision.decision_type == DecisionType.REQUEST_MORE_CONTEXT
    assert decision.recommended_action == "REQUEST_CONTEXT"


def test_manual_autonomy_does_not_apply_decisions() -> None:
    registry = DecisionRegistry()
    decision = registry.create_decision(
        evaluate_execution(
            ExecutionContext(
                workflow_run_id="run-manual",
                qa_status="FAILED",
                retry_count=0,
                max_retries=2,
                autonomy_level=AutonomyLevel.MANUAL,
                real_code_touched=True,
            )
        )
    )

    updated = registry.apply_decision(
        decision.decision_id,
        autonomy_level=AutonomyLevel.MANUAL,
        real_code_touched=True,
    )

    assert updated.status == DecisionStatus.PROPOSED
    assert updated.metadata["apply_blocked"] is True


def test_runtime_creates_execution_decision_review_when_required() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-INT-201")

    decisions = state.metadata["execution_decisions"]
    assert decisions
    latest = decisions[0]
    assert latest["requires_human_review"] is True
    assert latest["metadata"]["review_id"].startswith("review-")

    review = HumanReviewRegistry.default().get_review(latest["metadata"]["review_id"])
    assert review is not None
    assert review.review_type == ReviewType.EXECUTION_DECISION


def test_timeline_contains_decision_events() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-INT-202")
    timeline = build_workflow_timeline(state)

    assert any(event.event_type == "DECISION_PROPOSED" for event in timeline.events)


def test_phoenix_observer_exports_decision_metadata() -> None:
    exporter = RecordingSpanExporter()
    observer = PhoenixRuntimeObserver(
        PhoenixClient(span_exporter=exporter),
        environment="test",
    )
    runtime = DevelopmentRuntime(observer=observer)

    state = runtime.start_run(project="lummevia-os", issue_id="OS-INT-203")

    workflow_span = next(
        span for span in exporter.spans if span.name == "workflow_run:development_loop"
    )

    assert workflow_span.attributes["decision_count"] >= 1
    assert str(workflow_span.attributes["decision_id"]).startswith("decision-")
    assert workflow_span.attributes["decision_type"] in {
        DecisionType.RETRY.value,
        DecisionType.ESCALATE_REVIEW.value,
    }
    assert workflow_span.attributes["decision_status"] == DecisionStatus.PROPOSED.value
    assert workflow_span.attributes["autonomy_level"] == AutonomyLevel.MANUAL.value
    assert workflow_span.attributes["decision_requires_human_review"] is True
    assert workflow_span.attributes["confidence"] >= 0.0
    assert state.metadata["decision_id"].startswith("decision-")
