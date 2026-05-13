from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Sequence

from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SpanExportResult, SpanExporter

from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_runtime import DevelopmentRuntime
from lummevia_supervisor import (
    ExecutionHealthStatus,
    RecoveryActionType,
    SupervisorRegistry,
    WatchdogStatus,
)
from lummevia_timeline import build_workflow_timeline
from main import app


client = TestClient(app)


class RecordingSpanExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans = []

    def export(self, spans: Sequence[object]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


def test_supervisor_registry_creates_watchdog_updates_heartbeat_and_detects_stuck() -> None:
    registry = SupervisorRegistry()
    watchdog = registry.register_watchdog(
        workflow_run_id="run-1000",
        target_type="TaskExecutionSession",
        target_id="session-1000",
        timeout_seconds=30,
        metadata={"session_id": "session-1000"},
    )

    heartbeat = datetime.now(UTC) + timedelta(seconds=5)
    updated = registry.heartbeat(watchdog.watchdog_id, heartbeat_at=heartbeat)
    stale = updated.model_copy(update={"last_heartbeat_at": datetime.now(UTC) - timedelta(minutes=5)})
    registry._watchdogs[stale.watchdog_id] = stale

    stuck = registry.detect_stuck()

    assert updated.last_heartbeat_at == heartbeat
    assert stuck
    assert stuck[0].status == WatchdogStatus.STUCK
    assert stuck[0].metadata["stuck_detected"] is True


def test_supervisor_registry_creates_recovery_and_dead_letter_records() -> None:
    registry = SupervisorRegistry()
    action = registry.create_recovery_action(
        workflow_run_id="run-1001",
        target_type="TaskQueueItem",
        target_id="queue-item-1001",
        action_type=RecoveryActionType.RETRY,
        metadata={"retry_attempts": 1},
    )
    dead_letter = registry.mark_dead_letter(
        workflow_run_id="run-1001",
        task_id="OS-1001-T1",
        queue_item_id="queue-item-1001",
        reason="Retries exhausted",
        metadata={"recovery_action_id": action.action_id},
    )

    assert action.action_type == RecoveryActionType.RETRY
    assert registry.list_recovery_actions() == [action]
    assert dead_letter.workflow_run_id == "run-1001"
    assert dead_letter.queue_item_id == "queue-item-1001"
    assert registry.list_dead_letters() == [dead_letter]


def test_runtime_populates_supervisor_metadata_and_events() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-1002")

    assert state.metadata["health_status"] == ExecutionHealthStatus.HEALTHY.value
    assert state.metadata["watchdog_count"] >= 1
    assert state.metadata["supervisor_event_count"] >= 1
    assert state.metadata["supervisor"]
    assert any(
        event["event_type"] == "WATCHDOG_CREATED"
        for event in state.metadata["supervisor_events"]
    )
    assert any(
        event["event_type"] == "KILO_EXECUTION_RECORDED"
        for event in state.metadata["supervisor_events"]
    )


def test_runtime_queue_session_and_kilo_include_supervisor_fields() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-1003")

    queue_item = next(
        item
        for item in state.metadata["task_queue"]["items"]
        if item["queue_item_id"] == state.metadata["current_queue_item_id"]
    )
    session = state.metadata["sessions"][state.metadata["current_session_id"]]
    kilo_step = state.metadata["kilo_execution_by_step"]["qa_validation"]

    assert queue_item["metadata"]["health_status"] == ExecutionHealthStatus.HEALTHY.value
    assert "retry_attempts" in queue_item["metadata"]
    assert "watchdog_id" in session
    assert session["health_status"] == ExecutionHealthStatus.HEALTHY.value
    assert "recovery_history" in session
    assert kilo_step["health_status"] == ExecutionHealthStatus.HEALTHY.value
    assert kilo_step["watchdog_id"].startswith("watchdog-")
    assert kilo_step["strategy_id"].startswith("strategy-")
    assert kilo_step["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_cancel_workflow_releases_locks_and_marks_runtime_cancelled() -> None:
    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-1004")

    cancelled = SupervisorRegistry.default().cancel_workflow(state)

    assert cancelled.metadata["workflow_cancelled"] is True
    assert cancelled.metadata["health_status"] == ExecutionHealthStatus.CANCELLED.value
    assert cancelled.metadata["workspace_status"] == "RELEASED"
    assert cancelled.metadata["active_locks_count"] == 0
    assert any(
        event["event_type"] == "WORKFLOW_CANCELLED"
        for event in cancelled.metadata["supervisor_events"]
    )


def test_supervisor_endpoints_list_records_and_execute_actions() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-1005"},
    )
    assert runtime_response.status_code == 200
    payload = runtime_response.json()
    run_id = payload["run"]["run_id"]

    watchdogs_response = client.get("/supervisor/watchdogs")
    recovery_response = client.get("/supervisor/recovery-actions")
    dead_letters_response = client.get("/supervisor/dead-letters")
    detect_response = client.post("/supervisor/watchdogs/detect-stuck")
    cancel_response = client.post(f"/supervisor/workflows/{run_id}/cancel")

    assert watchdogs_response.status_code == 200
    assert any(item["workflow_run_id"] == run_id for item in watchdogs_response.json())
    assert recovery_response.status_code == 200
    assert dead_letters_response.status_code == 200
    assert detect_response.status_code == 200
    assert isinstance(detect_response.json(), list)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["metadata"]["workflow_cancelled"] is True


def test_supervisor_detect_stuck_creates_recovery_metadata_for_runtime_items() -> None:
    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-1006")
    registry = SupervisorRegistry.default()

    queue_item_watchdog = next(
        watchdog
        for watchdog in registry.list_watchdogs()
        if watchdog.workflow_run_id == state.run.run_id and watchdog.target_type == "TaskQueueItem"
    )
    registry._watchdogs[queue_item_watchdog.watchdog_id] = queue_item_watchdog.model_copy(
        update={
            "status": WatchdogStatus.ACTIVE,
            "last_heartbeat_at": datetime.now(UTC) - timedelta(hours=1),
        }
    )

    stuck_items = registry.detect_stuck(runtime_state=state)

    refreshed_queue_item = next(
        item
        for item in state.metadata["task_queue"]["items"]
        if item["queue_item_id"] == state.metadata["current_queue_item_id"]
    )

    assert stuck_items
    assert refreshed_queue_item["metadata"]["health_status"] in {
        ExecutionHealthStatus.STUCK.value,
        ExecutionHealthStatus.RECOVERING.value,
        ExecutionHealthStatus.DEAD_LETTER.value,
    }
    assert state.metadata["stuck_detected"] is True
    assert any(
        event["event_type"] == "RECOVERY_TRIGGERED"
        for event in state.metadata["supervisor_events"]
    )


def test_timeline_contains_supervisor_recovery_events() -> None:
    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-1007")
    registry = SupervisorRegistry.default()
    watchdog = next(
        item
        for item in registry.list_watchdogs()
        if item.workflow_run_id == state.run.run_id and item.target_type == "TaskQueueItem"
    )
    registry._watchdogs[watchdog.watchdog_id] = watchdog.model_copy(
        update={
            "status": WatchdogStatus.ACTIVE,
            "last_heartbeat_at": datetime.now(UTC) - timedelta(hours=1),
        }
    )
    registry.detect_stuck(runtime_state=state)

    timeline = build_workflow_timeline(state)
    event_types = {event.event_type for event in timeline.events}

    assert "WATCHDOG_CREATED" in event_types
    assert "EXECUTION_STUCK" in event_types
    assert "RECOVERY_TRIGGERED" in event_types
    assert "TASK_REQUEUED" in event_types


def test_phoenix_observer_exports_supervisor_metadata() -> None:
    exporter = RecordingSpanExporter()
    observer = PhoenixRuntimeObserver(
        PhoenixClient(span_exporter=exporter),
        environment="test",
    )
    runtime = DevelopmentRuntime(observer=observer)

    state = runtime.start_run(project="lummevia-os", issue_id="OS-1008")

    workflow_span = next(
        span for span in exporter.spans if span.name == "workflow_run:development_loop"
    )
    qa_span = next(span for span in exporter.spans if span.name == "step:qa_validation")

    assert workflow_span.attributes["health_status"] == ExecutionHealthStatus.HEALTHY.value
    assert str(workflow_span.attributes["watchdog_id"]).startswith("watchdog-")
    assert workflow_span.attributes["retry_attempts"] >= 0
    assert qa_span.attributes["health_status"] == ExecutionHealthStatus.HEALTHY.value
    assert str(qa_span.attributes["watchdog_id"]).startswith("watchdog-")
    assert qa_span.attributes["retry_attempts"] >= 0
    assert state.metadata["watchdog_id"].startswith("watchdog-")


def test_supervisor_recovery_actions_include_strategy_context() -> None:
    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-1009")
    registry = SupervisorRegistry.default()
    watchdog = next(
        item
        for item in registry.list_watchdogs()
        if item.workflow_run_id == state.run.run_id and item.target_type == "TaskQueueItem"
    )
    registry._watchdogs[watchdog.watchdog_id] = watchdog.model_copy(
        update={
            "status": WatchdogStatus.ACTIVE,
            "last_heartbeat_at": datetime.now(UTC) - timedelta(hours=1),
        }
    )

    registry.detect_stuck(runtime_state=state)

    action = next(
        item
        for item in registry.list_recovery_actions()
        if item.workflow_run_id == state.run.run_id
    )
    assert action.metadata["strategy_id"].startswith("strategy-")
    assert action.metadata["strategy_type"]
    assert action.metadata["risk_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
