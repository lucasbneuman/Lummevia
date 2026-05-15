from fastapi.testclient import TestClient

from lummevia_core import AgentRole
from lummevia_kilo import KiloExecutionMode
from lummevia_runtime import DevelopmentRuntime
from lummevia_sessions import SessionRegistry, SessionStatus
from main import app


client = TestClient(app)


def test_session_registry_creates_events_and_outputs() -> None:
    registry = SessionRegistry()
    session = registry.create_session(
        task_id="OS-900-T1",
        project="lummevia-os",
        issue_id="OS-900",
        role=AgentRole.PO,
        mode=KiloExecutionMode.PLAN,
        metadata={"run_id": "run-900"},
    )

    session = registry.add_event(
        session.session_id,
        type="SESSION_CREATED",
        message="Bootstrap session created.",
    )
    session = registry.add_output(
        session.session_id,
        output_type="task_package",
        content="TaskPackage ready for execution.",
    )
    session = registry.update_status(
        session.session_id,
        status=SessionStatus.RUNNING,
        attempts=1,
    )

    assert session.status == SessionStatus.RUNNING
    assert session.attempts == 1
    assert session.events[0].type == "SESSION_CREATED"
    assert session.events[-1].metadata["status"] == "RUNNING"
    assert session.outputs[0].output_type == "task_package"


def test_runtime_creates_session_and_tracks_kilo_lifecycle() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-901")

    session_id = state.metadata["current_session_id"]
    task_session = SessionRegistry.default().get_session(session_id)

    assert task_session is not None
    assert task_session.task_id == state.artifacts.current_task_package.task_id
    assert task_session.queue_id == state.metadata["queue_id"]
    assert task_session.queue_item_id == state.metadata["current_queue_item_id"]
    assert task_session.status == SessionStatus.COMPLETED
    assert state.metadata["task_package_sessions"][task_session.task_id] == session_id
    assert state.metadata["task_package_sessions"][task_session.task_id] == session_id
    assert state.metadata["sessions"][session_id]["status"] == "COMPLETED"
    assert any(output["output_type"] == "kilo_execution" for output in state.metadata["sessions"][session_id]["outputs"])
    assert any(
        execution["session_id"] == session_id
        for execution in state.metadata["kilo_executions"]
        if execution["task_id"] == task_session.task_id
    )


def test_runtime_records_waiting_review_before_final_completion() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-902")

    session_id = state.metadata["current_session_id"]
    task_session = SessionRegistry.default().get_session(session_id)

    assert task_session is not None
    assert any(
        event.metadata.get("status") == "WAITING_REVIEW"
        for session in SessionRegistry.default().list_sessions()
        for event in session.events
        if event.type == "STATUS_UPDATED"
    )
    assert any(
        event.metadata.get("status") == "COMPLETED"
        for event in task_session.events
        if event.type == "STATUS_UPDATED"
    )


def test_session_endpoints_list_and_get_runtime_sessions() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-903"},
    )
    assert runtime_response.status_code == 200
    session_id = runtime_response.json()["metadata"]["current_session_id"]

    list_response = client.get("/sessions")
    assert list_response.status_code == 200
    assert any(session["session_id"] == session_id for session in list_response.json())

    get_response = client.get(f"/sessions/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["session_id"] == session_id
    assert get_response.json()["status"] == "COMPLETED"
    assert get_response.json()["queue_id"].startswith("queue-")
    assert get_response.json()["queue_item_id"].startswith("queue-item-")
