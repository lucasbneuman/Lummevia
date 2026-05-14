from __future__ import annotations

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from lummevia_core import AgentRole, WorkflowRun, WorkflowRunStatus
from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_runtime import RuntimeState
from main import app

from lummevia_economics import (
    BudgetStatus,
    CostControlStatus,
    CostEstimator,
    EconomicsRegistry,
    ExecutionBudget,
    UsageEstimate,
    evaluate_cost_control_status,
)


client = TestClient(app)


class RecordingSpanExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans = []

    def export(self, spans) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def test_estimator_calculates_tokens_and_cost_by_tier() -> None:
    estimator = CostEstimator.default()

    estimate = estimator.estimate_usage(
        project="lummevia-os",
        provider="DEEPSEEK",
        model="deepseek-strong",
        role="PM",
        operation_type="pm_dry_run",
        prompt_length=800,
        output_length=400,
    )

    assert estimate.estimated_input_tokens > 0
    assert estimate.estimated_output_tokens > 0
    assert estimate.estimated_cost > 0
    assert estimate.metadata["cost_tier"] == "strong"


def test_budget_registry_create_list_get_and_record_usage() -> None:
    registry = EconomicsRegistry()
    budget = registry.create_budget(
        ExecutionBudget(
            project="lummevia-os",
            max_estimated_cost=10.0,
            max_model_calls=5,
            max_tokens_estimated=1000,
            metadata={"owner": "pm"},
        )
    )

    stored = registry.get_budget(budget.budget_id)
    assert stored is not None
    assert stored.project == "lummevia-os"
    assert registry.list_budgets()[0].budget_id == budget.budget_id

    usage = UsageEstimate(
        project="lummevia-os",
        provider="DEEPSEEK",
        model="deepseek-lite",
        role="PM",
        operation_type="pm_dry_run",
        estimated_input_tokens=100,
        estimated_output_tokens=50,
        estimated_cost=2.5,
        metadata={"budget_id": budget.budget_id},
    )
    updated_budget = registry.record_usage(usage)

    assert updated_budget is not None
    assert updated_budget.used_model_calls == 1
    assert updated_budget.used_tokens_estimated == 150
    assert updated_budget.used_estimated_cost == 2.5
    assert registry.get_usage_for_project("lummevia-os")[0].usage_id == usage.usage_id


def test_cost_control_status_thresholds_follow_policy() -> None:
    assert evaluate_cost_control_status(0.0) == CostControlStatus.ALLOW
    assert evaluate_cost_control_status(0.7) == CostControlStatus.WARN
    assert evaluate_cost_control_status(0.91) == CostControlStatus.DEGRADE
    assert evaluate_cost_control_status(1.01) == CostControlStatus.BLOCK


def test_budget_evaluation_progresses_to_warn_degrade_and_block() -> None:
    registry = EconomicsRegistry()
    budget = registry.create_budget(
        ExecutionBudget(
            project="lummevia-os",
            max_estimated_cost=10.0,
            max_model_calls=100,
            max_tokens_estimated=10000,
        )
    )

    def _record(cost: float) -> None:
        registry.record_usage(
            UsageEstimate(
                project="lummevia-os",
                provider="DEEPSEEK",
                model="deepseek-lite",
                role="DEV",
                operation_type="task_execution",
                estimated_input_tokens=100,
                estimated_output_tokens=50,
                estimated_cost=cost,
                metadata={"budget_id": budget.budget_id},
            )
        )

    _record(7.0)
    warn = registry.evaluate_budget(project="lummevia-os", budget_id=budget.budget_id)
    assert warn.status == CostControlStatus.WARN

    _record(2.2)
    degrade = registry.evaluate_budget(project="lummevia-os", budget_id=budget.budget_id)
    assert degrade.status == CostControlStatus.DEGRADE

    _record(1.0)
    block = registry.evaluate_budget(project="lummevia-os", budget_id=budget.budget_id)
    assert block.status == CostControlStatus.BLOCK
    assert registry.get_budget(budget.budget_id).status == BudgetStatus.EXCEEDED


def test_economics_endpoints_create_list_get_usage_and_evaluate() -> None:
    create_response = client.post(
        "/economics/budgets",
        json={
            "project": "lummevia-os",
            "max_estimated_cost": 5.0,
            "max_model_calls": 3,
            "max_tokens_estimated": 500,
            "metadata": {"source": "test"},
        },
    )

    assert create_response.status_code == 200
    budget_id = create_response.json()["budget_id"]

    list_response = client.get("/economics/budgets")
    assert list_response.status_code == 200
    assert any(item["budget_id"] == budget_id for item in list_response.json())

    get_response = client.get(f"/economics/budgets/{budget_id}")
    assert get_response.status_code == 200
    assert get_response.json()["budget_id"] == budget_id

    usage_response = client.get("/economics/usage", params={"project": "lummevia-os"})
    assert usage_response.status_code == 200
    assert usage_response.json() == []

    evaluate_response = client.post(
        "/economics/evaluate",
        json={
            "project": "lummevia-os",
            "budget_id": budget_id,
            "provider": "DEEPSEEK",
            "model": "deepseek-lite",
            "role": "PM",
            "operation_type": "pm_dry_run",
            "prompt_length": 1000,
            "output_length": 500,
        },
    )

    assert evaluate_response.status_code == 200
    body = evaluate_response.json()
    assert body["status"] in {
        CostControlStatus.ALLOW,
        CostControlStatus.WARN,
        CostControlStatus.DEGRADE,
        CostControlStatus.BLOCK,
    }
    assert body["recommended_action"]


def test_runtime_observer_exports_cost_metadata() -> None:
    exporter = RecordingSpanExporter()
    observer = PhoenixRuntimeObserver(
        PhoenixClient(span_exporter=exporter),
        environment="test",
    )
    state = RuntimeState(
        run=WorkflowRun(
            workflow_name="development_loop",
            project="lummevia-os",
            issue_id="OS-ECO-1",
            status=WorkflowRunStatus.RUNNING,
            current_step="pm_business_brief",
            events=[],
            metadata={},
        ),
        metadata={
            "budget_id": "budget-001",
            "estimated_cost_total": 4.5,
            "model_calls_count": 3,
            "tokens_estimated_total": 1200,
            "cost_control_status": "WARN",
            "cost_recommendation": "use_lite_or_fake_for_next_step",
        },
    )

    with observer.observe_workflow_run(state):
        state.run.status = WorkflowRunStatus.COMPLETED

    span = next(span for span in exporter.spans if span.name == "workflow_run:development_loop")
    assert span.attributes["budget_id"] == "budget-001"
    assert span.attributes["estimated_cost_total"] == 4.5
    assert span.attributes["model_calls_count"] == 3
    assert span.attributes["tokens_estimated_total"] == 1200
    assert span.attributes["cost_control_status"] == "WARN"
    assert span.attributes["cost_recommendation"] == "use_lite_or_fake_for_next_step"
