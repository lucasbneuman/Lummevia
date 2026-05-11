from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_runtime_post_executes_workflow_and_returns_final_state() -> None:
    response = client.post(
        "/runtime/development/run",
        json={
            "project": "lummevia-os",
            "issue_id": "OS-100",
        },
    )

    assert response.status_code == 200
    body = response.json()

    assert body["run"]["workflow_name"] == "development_loop"
    assert body["run"]["project"] == "lummevia-os"
    assert body["run"]["issue_id"] == "OS-100"
    assert body["run"]["status"] == "COMPLETED"
    assert body["run"]["current_step"] == "po_final_validation"
    assert body["current_role"] == "PO"
    assert body["loop_count"] == 1
    assert body["max_loop_count"] == 1
    assert body["artifacts"]["business_brief"]["issue_id"] == "OS-100"
    assert body["artifacts"]["business_brief"]["business_brief_status"] == "approved"
    assert body["artifacts"]["business_brief"]["founder_approved"] is True
    assert body["artifacts"]["task_plan"]["issue_id"] == "OS-100"
    assert len(body["artifacts"]["task_packages"]) >= 2
    assert body["artifacts"]["current_task_package"]["task_id"].startswith("OS-100-T")
    assert body["artifacts"]["validation_package"]["status"] == "PASSED"
    assert body["artifacts"]["pull_request"]["status"] == "OPEN"
    assert body["artifacts"]["pull_request"]["url"].endswith("/pull/1002")
    assert body["artifacts"]["quality_approval"]["pr_ok"] is True
    assert body["artifacts"]["final_validation"]["approved"] is True
    assert body["run"]["events"]

    github_pr_started_index = next(
        index
        for index, event in enumerate(body["run"]["events"])
        if event["step_name"] == "github_pr" and event["metadata"]["type"] == "STEP_STARTED"
    )
    qa_pass_completed_index = max(
        index
        for index, event in enumerate(body["run"]["events"])
        if event["step_name"] == "qa_validation"
        and event["metadata"]["type"] == "STEP_COMPLETED"
        and event["metadata"].get("validation_status") == "PASSED"
    )
    qc_started_index = next(
        index
        for index, event in enumerate(body["run"]["events"])
        if event["step_name"] == "qc_quality_approval"
        and event["metadata"]["type"] == "STEP_STARTED"
    )
    founder_approval_completed_index = next(
        index
        for index, event in enumerate(body["run"]["events"])
        if event["step_name"] == "founder_business_approval"
        and event["metadata"]["type"] == "STEP_COMPLETED"
        and event["metadata"].get("founder_approved") is True
    )
    po_started_index = next(
        index
        for index, event in enumerate(body["run"]["events"])
        if event["step_name"] == "po_execution_package"
        and event["metadata"]["type"] == "STEP_STARTED"
    )
    task_plan_started_index = next(
        index
        for index, event in enumerate(body["run"]["events"])
        if event["step_name"] == "po_task_plan"
        and event["metadata"]["type"] == "STEP_STARTED"
    )
    task_packages_started_index = next(
        index
        for index, event in enumerate(body["run"]["events"])
        if event["step_name"] == "po_task_packages"
        and event["metadata"]["type"] == "STEP_STARTED"
    )
    dev_started_index = next(
        index
        for index, event in enumerate(body["run"]["events"])
        if event["step_name"] == "dev_implementation"
        and event["metadata"]["type"] == "STEP_STARTED"
    )

    assert qa_pass_completed_index < github_pr_started_index < qc_started_index
    assert founder_approval_completed_index < po_started_index
    assert po_started_index < task_plan_started_index < task_packages_started_index < dev_started_index


def test_runtime_post_generates_unique_run_ids() -> None:
    payload = {
        "project": "lummevia-os",
        "issue_id": "OS-101",
    }

    first = client.post("/runtime/development/run", json=payload)
    second = client.post("/runtime/development/run", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["run"]["run_id"] != second.json()["run"]["run_id"]


def test_runtime_get_returns_existing_run() -> None:
    created = client.post(
        "/runtime/development/run",
        json={
            "project": "lummevia-os",
            "issue_id": "OS-102",
        },
    )
    run_id = created.json()["run"]["run_id"]

    response = client.get(f"/runtime/development/run/{run_id}")

    assert response.status_code == 200
    assert response.json()["run"]["run_id"] == run_id
    assert response.json()["artifacts"]["pull_request"]["status"] == "OPEN"


def test_runtime_get_returns_404_for_missing_run() -> None:
    response = client.get("/runtime/development/run/run-missing")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Runtime run 'run-missing' not found.",
    }


def test_runtime_post_persists_final_run_when_repository_is_active(monkeypatch) -> None:
    from app.api.routes import runtime as runtime_routes
    from lummevia_runtime import DevelopmentRuntime
    from lummevia_runtime.persistence import (
        SqlAlchemyWorkflowRunRepository,
        create_database_engine,
        create_session_factory,
        create_tables,
    )

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_tables(engine)
    repository = SqlAlchemyWorkflowRunRepository(create_session_factory(engine))
    monkeypatch.setattr(
        runtime_routes,
        "runtime_service",
        DevelopmentRuntime(repository=repository),
    )
    monkeypatch.setattr(runtime_routes, "runtime_repository", repository)

    response = client.post(
        "/runtime/development/run",
        json={
            "project": "lummevia-os",
            "issue_id": "OS-103",
        },
    )

    assert response.status_code == 200
    run_id = response.json()["run"]["run_id"]
    recovered = repository.get_run(run_id)

    assert recovered.run.run_id == run_id
    assert recovered.run.status.value == "COMPLETED"


def test_runtime_get_falls_back_to_persisted_run(monkeypatch) -> None:
    from app.api.routes import runtime as runtime_routes
    from lummevia_runtime import DevelopmentRuntime
    from lummevia_runtime.persistence import (
        SqlAlchemyWorkflowRunRepository,
        create_database_engine,
        create_session_factory,
        create_tables,
    )

    runtime = DevelopmentRuntime()
    state = runtime.start_run(project="lummevia-os", issue_id="OS-104")
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_tables(engine)
    repository = SqlAlchemyWorkflowRunRepository(create_session_factory(engine))
    repository.save_run(state)

    monkeypatch.setattr(runtime_routes, "runtime_service", DevelopmentRuntime())
    monkeypatch.setattr(runtime_routes, "runtime_repository", repository)

    response = client.get(f"/runtime/development/run/{state.run.run_id}")

    assert response.status_code == 200
    assert response.json()["run"]["run_id"] == state.run.run_id
    assert response.json()["run"]["issue_id"] == "OS-104"


def test_runtime_list_returns_persisted_runs_when_repository_is_active(monkeypatch) -> None:
    from app.api.routes import runtime as runtime_routes
    from lummevia_runtime import DevelopmentRuntime
    from lummevia_runtime.persistence import (
        SqlAlchemyWorkflowRunRepository,
        create_database_engine,
        create_session_factory,
        create_tables,
    )

    runtime = DevelopmentRuntime()
    first = runtime.start_run(project="lummevia-os", issue_id="OS-105")
    second = runtime.start_run(project="lummevia-os", issue_id="OS-106")
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_tables(engine)
    repository = SqlAlchemyWorkflowRunRepository(create_session_factory(engine))
    repository.save_run(first)
    repository.save_run(second)

    monkeypatch.setattr(runtime_routes, "runtime_repository", repository)

    response = client.get("/runtime/development/runs")

    assert response.status_code == 200
    assert [run["run"]["issue_id"] for run in response.json()[:2]] == ["OS-106", "OS-105"]
