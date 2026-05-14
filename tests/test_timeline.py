from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from lummevia_core import AgentRole
from lummevia_kilo import KiloExecutionMode
from lummevia_runtime import DevelopmentRuntime
from lummevia_sessions import SessionEvent, SessionRegistry, SessionStatus
from lummevia_timeline import (
    TimelineEvent,
    TimelineRegistry,
    TimelineSourceType,
    build_workflow_timeline,
)
from main import app


client = TestClient(app)


def test_timeline_registry_creates_adds_and_lists_timelines() -> None:
    registry = TimelineRegistry()
    timeline = registry.create_timeline(
        workflow_run_id="run-001",
        project="lummevia-os",
        issue_id="OS-001",
        metadata={"replay_available": True},
    )

    created_event = TimelineEvent(
        event_id="timeline-event-001",
        workflow_run_id="run-001",
        event_type="SESSION_CREATED",
        source_type=TimelineSourceType.SESSION,
        source_id="session-001",
        title="Task session created",
        description="A task execution session was created.",
        created_at=datetime.now(UTC),
        metadata={"task_id": "OS-001-T1"},
    )
    registry.add_event("run-001", created_event)

    recovered = registry.get_timeline("run-001")

    assert recovered is not None
    assert recovered.timeline_id == timeline.timeline_id
    assert recovered.events == [created_event]
    assert registry.list_timelines() == [recovered]


def test_timeline_builder_aggregates_sources_in_chronological_order() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-801")
    timeline = build_workflow_timeline(state)

    assert timeline.workflow_run_id == state.run.run_id
    assert timeline.project == "lummevia-os"
    assert timeline.issue_id == "OS-801"
    assert timeline.metadata["replay_available"] is True
    assert timeline.metadata["timeline_event_count"] == len(timeline.events)
    assert "WORKFLOW" in timeline.metadata["timeline_sources"]
    assert "CONVERSATION" in timeline.metadata["timeline_sources"]
    assert "SESSION" in timeline.metadata["timeline_sources"]
    assert "REVIEW" in timeline.metadata["timeline_sources"]
    assert "MEMORY" in timeline.metadata["timeline_sources"]

    created_at_values = [event.created_at for event in timeline.events]
    assert created_at_values == sorted(created_at_values)
    assert any(event.source_type == TimelineSourceType.CONVERSATION for event in timeline.events)
    assert any(
        event.event_type == "QA_REVIEW_PENDING" and event.source_type == TimelineSourceType.REVIEW
        for event in timeline.events
    )
    assert any(
        event.event_type == "SESSION_STATUS_UPDATED"
        and event.metadata.get("status") == SessionStatus.WAITING_REVIEW.value
        for event in timeline.events
    )


def test_timeline_builder_sorts_manual_events_chronologically() -> None:
    registry = SessionRegistry.default()
    session = registry.create_session(
        task_id="OS-802-T1",
        project="lummevia-os",
        issue_id="OS-802",
        role=AgentRole.DEV,
        mode=KiloExecutionMode.CODE,
        metadata={"run_id": "run-802", "workflow": "development_loop"},
    )
    early = datetime.now(UTC)
    late = early + timedelta(minutes=2)
    session = session.model_copy(
        update={
            "events": [
                SessionEvent(
                    event_id="session-event-late",
                    type="LATE_EVENT",
                    message="Late event",
                    created_at=late,
                    metadata={},
                ),
                SessionEvent(
                    event_id="session-event-early",
                    type="EARLY_EVENT",
                    message="Early event",
                    created_at=early,
                    metadata={},
                ),
            ]
        }
    )
    registry._sessions[session.session_id] = session

    timeline = build_workflow_timeline(
        workflow_run_id="run-802",
        project="lummevia-os",
        issue_id="OS-802",
        sessions=[session],
    )

    assert [event.event_type for event in timeline.events[-2:]] == [
        "EARLY_EVENT",
        "LATE_EVENT",
    ]


def test_runtime_registers_timeline_metadata_and_registry_snapshot() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-803")
    timeline = TimelineRegistry.default().get_timeline(state.run.run_id)

    assert timeline is not None
    assert state.metadata["timeline_id"] == timeline.timeline_id
    assert state.metadata["timeline_event_count"] == len(timeline.events)
    assert state.metadata["replay_available"] is True
    assert "WORKFLOW" in state.metadata["timeline_sources"]
    assert any(event.event_type == "FOUNDER_RESPONSE_RECEIVED" for event in timeline.events)
    assert any(event.event_type == "PM_QUESTION_SENT" for event in timeline.events)
    assert any(event.event_type == "BRIEF_DRAFT_CREATED" for event in timeline.events)
    assert any(event.event_type == "BRIEF_APPROVED" for event in timeline.events)
    assert any(event.event_type == "QUEUE_CREATED" for event in timeline.events)
    assert any(event.event_type == "TASK_QUEUED" for event in timeline.events)
    assert any(event.event_type == "TASK_READY" for event in timeline.events)
    assert any(event.event_type == "TASK_STARTED" for event in timeline.events)
    assert any(event.event_type == "TASK_COMPLETED" for event in timeline.events)
    assert any(event.event_type == "CODE_CHANGE_DETECTED" for event in timeline.events)
    assert any(event.event_type == "CODE_CHANGE_VALIDATED" for event in timeline.events)
    assert any(event.event_type == "STRATEGY_SELECTED" for event in timeline.events)


def test_timeline_endpoints_list_and_get_reconstructed_timeline() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-804"},
    )
    assert runtime_response.status_code == 200
    run_id = runtime_response.json()["run"]["run_id"]

    list_response = client.get("/timelines")
    assert list_response.status_code == 200
    assert any(timeline["workflow_run_id"] == run_id for timeline in list_response.json())

    get_response = client.get(f"/timelines/{run_id}")
    assert get_response.status_code == 200
    body = get_response.json()

    assert body["workflow_run_id"] == run_id
    assert body["metadata"]["replay_available"] is True
    assert body["metadata"]["timeline_event_count"] == len(body["events"])
    assert any(event["event_type"] == "QA_REVIEW_PENDING" for event in body["events"])
    assert any(event["event_type"] == "BRIEF_DRAFT_CREATED" for event in body["events"])
