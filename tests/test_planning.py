from __future__ import annotations

from collections.abc import Sequence

from opentelemetry.sdk.trace.export import SpanExportResult, SpanExporter

from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_planning import (
    AdaptivePlanRegistry,
    AdaptivePlanStatus,
    AdaptivePlanningContext,
    MutationType,
    evaluate_adaptive_plan,
)
from lummevia_reviews import HumanReviewRegistry, ReviewType
from lummevia_runtime import DevelopmentRuntime
from lummevia_runtime.planning import build_adaptive_planning_context, propose_adaptive_plan
from lummevia_timeline import build_workflow_timeline


class RecordingSpanExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans = []

    def export(self, spans: Sequence[object]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def test_large_diff_proposes_split_task() -> None:
    plan = evaluate_adaptive_plan(
        AdaptivePlanningContext(
            workflow_run_id="run-plan-large-diff",
            project="lummevia-os",
            issue_id="OS-PLAN-1",
            source_task_id="OS-PLAN-1-T1",
            trigger_reason="large_diff",
            files_changed_count=12,
        )
    )

    assert MutationType.SPLIT_TASK in {mutation.mutation_type for mutation in plan.mutations}
    assert len(plan.proposed_task_packages) == 2


def test_repeated_qa_fail_proposes_insert_review() -> None:
    plan = evaluate_adaptive_plan(
        AdaptivePlanningContext(
            workflow_run_id="run-plan-qa",
            project="lummevia-os",
            issue_id="OS-PLAN-2",
            source_task_id="OS-PLAN-2-T1",
            trigger_reason="qa_repeated_fail",
            qa_fail_count=2,
        )
    )

    assert MutationType.INSERT_REVIEW in {mutation.mutation_type for mutation in plan.mutations}


def test_missing_context_proposes_regenerate_prompt() -> None:
    plan = evaluate_adaptive_plan(
        AdaptivePlanningContext(
            workflow_run_id="run-plan-context",
            project="lummevia-os",
            issue_id="OS-PLAN-3",
            source_task_id="OS-PLAN-3-T1",
            trigger_reason="missing_context",
            missing_context=True,
        )
    )

    assert MutationType.REGENERATE_PROMPT in {mutation.mutation_type for mutation in plan.mutations}


def test_dead_letter_risk_proposes_escalate_task() -> None:
    plan = evaluate_adaptive_plan(
        AdaptivePlanningContext(
            workflow_run_id="run-plan-dead-letter",
            project="lummevia-os",
            issue_id="OS-PLAN-4",
            source_task_id="OS-PLAN-4-T1",
            trigger_reason="dead_letter_risk",
            retry_count=2,
            max_retries=2,
            dead_letter_risk=True,
        )
    )

    assert MutationType.ESCALATE_TASK in {mutation.mutation_type for mutation in plan.mutations}


def test_sensitive_mutations_create_human_review() -> None:
    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-PLAN-5")

    plan = propose_adaptive_plan(
        state,
        context=build_adaptive_planning_context(
            state,
            trigger_reason="large_diff",
            source_task_id=state.metadata["current_queue_task_id"],
            files_changed_count=12,
        ),
    )

    review_id = plan.metadata["review_id"]
    review = HumanReviewRegistry.default().get_review(review_id)

    assert review is not None
    assert review.review_type == ReviewType.ADAPTIVE_PLAN


def test_no_autoapply_by_default() -> None:
    plan = AdaptivePlanRegistry.default().create_plan(
        evaluate_adaptive_plan(
            AdaptivePlanningContext(
                workflow_run_id="run-plan-manual",
                project="lummevia-os",
                issue_id="OS-PLAN-6",
                source_task_id="OS-PLAN-6-T1",
                trigger_reason="large_diff",
                files_changed_count=9,
            )
        )
    )

    assert plan.status == AdaptivePlanStatus.PROPOSED
    assert plan.metadata["auto_apply_enabled"] is False


def test_runtime_creates_adaptive_plan_and_timeline_events() -> None:
    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-PLAN-7")
    timeline = build_workflow_timeline(state)

    assert state.metadata["adaptive_plan_count"] >= 1
    assert any(event.event_type == "ADAPTIVE_PLAN_CREATED" for event in timeline.events)
    assert any(event.event_type == "GRAPH_MUTATION_PROPOSED" for event in timeline.events)


def test_phoenix_observer_exports_adaptive_planning_metadata() -> None:
    exporter = RecordingSpanExporter()
    observer = PhoenixRuntimeObserver(
        PhoenixClient(span_exporter=exporter),
        environment="test",
    )
    runtime = DevelopmentRuntime(observer=observer)

    state = runtime.start_run(project="lummevia-os", issue_id="OS-PLAN-8")
    workflow_span = next(
        span for span in exporter.spans if span.name == "workflow_run:development_loop"
    )

    assert workflow_span.attributes["adaptive_plan_count"] >= 1
    assert workflow_span.attributes["mutation_count"] >= 1
    assert str(workflow_span.attributes["adaptive_plan_id"]).startswith("adaptive-plan-")
    assert workflow_span.attributes["adaptive_plan_status"] == AdaptivePlanStatus.PROPOSED.value
    assert state.metadata["adaptive_plan_id"].startswith("adaptive-plan-")
