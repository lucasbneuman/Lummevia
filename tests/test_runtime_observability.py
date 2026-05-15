from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

from main import app
from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_kilo import KiloExecutionClient, KiloExecutionRequest, KiloRetryPolicy
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


class PhoenixRetryKiloClient(KiloExecutionClient):
    def execute(self, request: KiloExecutionRequest):
        metadata = {**request.metadata}
        if metadata.get("step_name") == "dev_implementation":
            metadata["fail_first_attempt"] = True
            metadata["max_attempts"] = 2
        max_attempts = int(metadata.get("max_attempts", request.retry_policy.max_attempts))
        return super().execute(
            request.model_copy(
                update={
                    "metadata": metadata,
                    "retry_policy": KiloRetryPolicy(max_attempts=max_attempts),
                }
            )
        )


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
    assert state.run.current_step == "workflow_completed"


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
    assert str(workflow_span.attributes["thread_id"]).startswith("thread-")
    assert workflow_span.attributes["conversation_status"] == "APPROVED"
    assert workflow_span.attributes["conversation_phase"] == "APPROVED"
    assert workflow_span.attributes["iteration_count"] == 1
    assert workflow_span.attributes["brief_version"] == 1
    assert workflow_span.attributes["pending_questions_count"] == 0
    assert workflow_span.attributes["message_count"] >= 4
    assert str(workflow_span.attributes["session_id"]).startswith("session-")
    assert workflow_span.attributes["session_status"] == "COMPLETED"
    assert workflow_span.attributes["session_role"] == "QA"
    assert workflow_span.attributes["session_attempts"] >= 1
    assert workflow_span.attributes["output_count"] >= 1
    assert workflow_span.attributes["event_count"] >= 1
    assert workflow_span.attributes["memory_records_created"] >= 1
    assert workflow_span.attributes["project_memory_count"] >= 1
    assert "BUSINESS_DECISION" in workflow_span.attributes["memory_categories"]
    assert workflow_span.attributes["timeline_event_count"] >= len(state.run.events)
    assert "WORKFLOW" in workflow_span.attributes["timeline_sources"]
    assert workflow_span.attributes["replay_available"] is True
    assert str(workflow_span.attributes["queue_id"]).startswith("queue-")
    assert workflow_span.attributes["queue_size"] >= 2
    assert workflow_span.attributes["completed_count"] >= 1
    assert str(workflow_span.attributes["current_queue_item_id"]).startswith("queue-item-")
    assert str(workflow_span.attributes["workspace_id"]).startswith("workspace-")
    assert str(workflow_span.attributes["branch_name"]).startswith("lummevia/")
    assert "kilo-workspaces" in str(workflow_span.attributes["worktree_path"])
    assert workflow_span.attributes["resource_locks_count"] >= 3
    assert workflow_span.attributes["active_locks_count"] >= 0
    assert workflow_span.attributes["workspace_status"] == "RELEASED"
    assert str(workflow_span.attributes["allocation_id"]).startswith("allocation-")
    assert workflow_span.attributes["allocation_status"] == "GRANTED"
    assert workflow_span.attributes["capacity_used_slots"] >= 1
    assert workflow_span.attributes["capacity_max_slots"] >= 1
    assert workflow_span.attributes["allocated_resources_count"] >= 1
    assert str(workflow_span.attributes["strategy_id"]).startswith("strategy-")
    assert workflow_span.attributes["strategy_type"] in {
        "SAFE",
        "BALANCED",
        "VALIDATION_HEAVY",
        "RECOVERY",
        "COST_OPTIMIZED",
        "AGGRESSIVE",
    }
    assert workflow_span.attributes["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert workflow_span.attributes["qa_level"] in {"BASIC", "STANDARD", "STRICT", "PARANOID"}
    assert workflow_span.attributes["sandbox_level"] in {"NONE", "BASIC", "ISOLATED", "STRICT"}
    assert workflow_span.attributes["selected_model"]
    assert workflow_span.attributes["selected_provider"]
    assert workflow_span.attributes["execution_mode"]

    step_names = {span.name for span in exporter.spans}
    assert "step:dev_implementation" in step_names
    assert "step:qa_validation" in step_names
    assert "step:dev_qa_iteration" in step_names


def test_phoenix_runtime_observer_exports_kilo_metadata_on_steps() -> None:
    exporter = RecordingSpanExporter()
    observer = PhoenixRuntimeObserver(
        PhoenixClient(span_exporter=exporter),
        environment="test",
    )
    runtime = DevelopmentRuntime(observer=observer)

    state = runtime.start_run(project="lummevia-os", issue_id="OS-205")

    assert state.run.status.value == "COMPLETED"

    dev_span = next(span for span in exporter.spans if span.name == "step:dev_implementation")
    qa_spans = [span for span in exporter.spans if span.name == "step:qa_validation"]
    qa_span = qa_spans[0]

    assert dev_span.attributes["kilo_mode"] == "CODE"
    assert dev_span.attributes["kilo_status"] == "SUCCESS"
    assert str(dev_span.attributes["session_id"]).startswith("session-")
    assert dev_span.attributes["retry_count"] == 0
    assert dev_span.attributes["attempts_count"] == 1
    assert dev_span.attributes["final_status"] == "SUCCESS"
    assert dev_span.attributes["role"] == "DEV"
    assert str(dev_span.attributes["task_id"]).startswith("OS-205-")
    assert str(dev_span.attributes["execution_id"]).startswith("kilo-")
    assert str(dev_span.attributes["queue_id"]).startswith("queue-")
    assert str(dev_span.attributes["queue_item_id"]).startswith("queue-item-")
    assert str(dev_span.attributes["workspace_id"]).startswith("workspace-")
    assert str(dev_span.attributes["branch_name"]).startswith("lummevia/")
    assert "kilo-workspaces" in str(dev_span.attributes["worktree_path"])
    assert dev_span.attributes["workspace_status"] == "ACTIVE"
    assert str(dev_span.attributes["allocation_id"]).startswith("allocation-")
    assert dev_span.attributes["allocation_status"] == "GRANTED"
    assert dev_span.attributes["capacity_used_slots"] >= 1
    assert dev_span.attributes["capacity_max_slots"] >= 1
    assert dev_span.attributes["allocated_resources_count"] >= 1
    assert dev_span.attributes["real_execution"] is False
    assert dev_span.attributes["safety_status"] == "DISABLED"
    assert str(dev_span.attributes["change_set_id"]).startswith("change-set-")
    assert dev_span.attributes["artifact_count"] >= 1
    assert str(dev_span.attributes["strategy_id"]).startswith("strategy-")
    assert dev_span.attributes["execution_mode"]
    assert dev_span.attributes["selected_model"]
    assert dev_span.attributes["selected_provider"]

    assert qa_span.attributes["kilo_mode"] == "DEBUG"
    assert qa_span.attributes["kilo_status"] == "SUCCESS"
    assert str(qa_span.attributes["session_id"]).startswith("session-")
    assert qa_span.attributes["retry_count"] == 0
    assert qa_span.attributes["attempts_count"] == 1
    assert qa_span.attributes["final_status"] == "SUCCESS"
    assert qa_span.attributes["role"] == "QA"
    assert str(qa_span.attributes["task_id"]).startswith("OS-205-")
    assert str(qa_span.attributes["execution_id"]).startswith("kilo-")
    assert str(qa_span.attributes["queue_id"]).startswith("queue-")
    assert str(qa_span.attributes["queue_item_id"]).startswith("queue-item-")
    assert str(qa_span.attributes["workspace_id"]).startswith("workspace-")
    assert str(qa_span.attributes["branch_name"]).startswith("lummevia/")
    assert "kilo-workspaces" in str(qa_span.attributes["worktree_path"])
    assert str(qa_span.attributes["allocation_id"]).startswith("allocation-")
    assert qa_span.attributes["allocation_status"] == "GRANTED"
    assert qa_span.attributes["real_execution"] is False
    assert qa_span.attributes["safety_status"] == "DISABLED"
    assert qa_span.attributes["validation_status"] == "FAILED"
    assert str(qa_span.attributes["qa_checked_change_set_id"]).startswith("change-set-")
    assert str(qa_span.attributes["strategy_id"]).startswith("strategy-")

    founder_review_span = next(
        span for span in exporter.spans if span.name == "step:founder_business_approval"
    )
    assert founder_review_span.attributes["conversation_phase"] == "APPROVED"
    assert founder_review_span.attributes["brief_version"] == 1
    assert founder_review_span.attributes["review_type"] == "BUSINESS_BRIEF"
    assert founder_review_span.attributes["review_status"] == "COMPLETED"
    assert founder_review_span.attributes["review_decision"] == "APPROVED"
    assert str(founder_review_span.attributes["review_id"]).startswith("review-")
    assert str(founder_review_span.attributes["thread_id"]).startswith("thread-")

    assert qa_spans[0].attributes["review_type"] == "QA_VALIDATION"
    assert qa_spans[0].attributes["review_status"] == "PENDING"
    assert "review_decision" not in qa_spans[0].attributes
    assert qa_spans[-1].attributes["review_type"] == "QA_VALIDATION"
    assert qa_spans[-1].attributes["review_status"] == "COMPLETED"
    assert qa_spans[-1].attributes["review_decision"] == "APPROVED"


def test_phoenix_runtime_observer_exports_kilo_retry_metadata_on_steps() -> None:
    exporter = RecordingSpanExporter()
    observer = PhoenixRuntimeObserver(
        PhoenixClient(span_exporter=exporter),
        environment="test",
    )
    runtime = DevelopmentRuntime(
        observer=observer,
        kilo_client=PhoenixRetryKiloClient(),
    )

    state = runtime.start_run(project="lummevia-os", issue_id="OS-206")

    assert state.run.status.value == "COMPLETED"

    dev_span = next(span for span in exporter.spans if span.name == "step:dev_implementation")

    assert dev_span.attributes["kilo_status"] == "SUCCESS"
    assert str(dev_span.attributes["session_id"]).startswith("session-")
    assert dev_span.attributes["retry_count"] == 1
    assert dev_span.attributes["attempts_count"] == 2
    assert dev_span.attributes["final_status"] == "SUCCESS"


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
