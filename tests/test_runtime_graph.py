from lummevia_core import (
    AgentRole,
    BusinessBrief,
    ExecutionPackage,
    ImplementationPackage,
    QualityApproval,
    ValidationPackage,
    ValidationStatus,
    WorkflowRunStatus,
)
from lummevia_runtime import DevelopmentRuntime, RuntimeNotFoundError, RuntimeState, RuntimeRegistry
from lummevia_runtime.graph import build_development_graph


def test_build_development_graph_returns_compiled_graph() -> None:
    graph = build_development_graph()

    assert graph is not None
    assert hasattr(graph, "invoke")


def test_runtime_executes_complete_workflow() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-1")

    assert isinstance(state, RuntimeState)
    assert state.run.workflow_name == "development_loop"
    assert state.run.status == WorkflowRunStatus.COMPLETED
    assert state.run.current_step == "po_final_validation"
    assert state.current_role == AgentRole.PO
    assert state.artifacts.business_brief is not None
    assert state.artifacts.execution_package is not None
    assert state.artifacts.implementation_package is not None
    assert state.artifacts.validation_package is not None
    assert state.artifacts.pull_request is not None
    assert state.artifacts.quality_approval is not None
    assert state.artifacts.final_validation is not None


def test_runtime_artifacts_reuse_core_contract_types() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-2")

    assert isinstance(state.artifacts.business_brief, BusinessBrief)
    assert isinstance(state.artifacts.execution_package, ExecutionPackage)
    assert isinstance(state.artifacts.implementation_package, ImplementationPackage)
    assert isinstance(state.artifacts.validation_package, ValidationPackage)
    assert isinstance(state.artifacts.pull_request, dict)
    assert isinstance(state.artifacts.quality_approval, QualityApproval)


def test_dev_qa_loop_occurs_exactly_once() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-3")
    loop_events = [
        event for event in state.run.events if event.metadata.get("type") == "LOOP_REENTERED"
    ]

    assert state.loop_count == 1
    assert len(loop_events) == 1
    assert state.artifacts.validation_package is not None
    assert state.artifacts.validation_package.status == ValidationStatus.PASSED


def test_runtime_registers_step_events() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-4")
    event_types = [event.metadata["type"] for event in state.run.events]
    github_pr_events = [event for event in state.run.events if event.step_name == "github_pr"]

    assert "STEP_STARTED" in event_types
    assert "STEP_COMPLETED" in event_types
    assert "LOOP_REENTERED" in event_types
    assert [event.metadata["type"] for event in github_pr_events] == [
        "STEP_STARTED",
        "STEP_COMPLETED",
    ]


def test_github_pr_occurs_after_qa_pass_and_before_qc() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-4A")
    events = state.run.events
    last_qa_completed_index = max(
        index
        for index, event in enumerate(events)
        if event.step_name == "qa_validation"
        and event.metadata["type"] == "STEP_COMPLETED"
        and event.metadata.get("validation_status") == "PASSED"
    )
    github_pr_started_index = next(
        index
        for index, event in enumerate(events)
        if event.step_name == "github_pr"
        and event.metadata["type"] == "STEP_STARTED"
    )
    qc_started_index = next(
        index
        for index, event in enumerate(events)
        if event.step_name == "qc_quality_approval"
        and event.metadata["type"] == "STEP_STARTED"
    )

    assert last_qa_completed_index < github_pr_started_index < qc_started_index
    assert state.artifacts.pull_request is not None
    assert state.artifacts.pull_request["status"] == "OPEN"
    assert state.artifacts.pull_request["branch"] == state.artifacts.implementation_package.branch


def test_runtime_generates_unique_run_ids() -> None:
    runtime = DevelopmentRuntime()

    first = runtime.start_run(project="lummevia-os", issue_id="OS-5")
    second = runtime.start_run(project="lummevia-os", issue_id="OS-5")

    assert first.run.run_id != second.run.run_id


def test_runtime_registry_stores_and_recovers_runs() -> None:
    registry = RuntimeRegistry()
    runtime = DevelopmentRuntime(registry=registry)

    state = runtime.start_run(project="lummevia-os", issue_id="OS-6")
    recovered = registry.get(state.run.run_id)

    assert recovered.run.run_id == state.run.run_id
    assert recovered.run.status == WorkflowRunStatus.COMPLETED


def test_runtime_registry_raises_for_missing_run() -> None:
    registry = RuntimeRegistry()

    try:
        registry.get("run-missing")
    except RuntimeNotFoundError as exc:
        assert str(exc) == "Runtime run 'run-missing' not found."
    else:
        raise AssertionError("Expected RuntimeNotFoundError for missing run.")
