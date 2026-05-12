from lummevia_core import (
    AgentRole,
    BusinessBrief,
    ExecutionPackage,
    ImplementationPackage,
    QualityApproval,
    TaskPackage,
    TaskPlan,
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
    assert state.artifacts.business_brief.business_brief_status == "approved"
    assert state.artifacts.business_brief.founder_approved is True
    assert state.metadata["thread_id"].startswith("thread-")
    assert state.metadata["conversation_status"] == "APPROVED"
    assert state.metadata["iteration_count"] == 1
    assert state.artifacts.execution_package is not None
    assert state.artifacts.task_plan is not None
    assert state.artifacts.task_packages
    assert state.metadata["queue_id"].startswith("queue-")
    assert state.metadata["current_queue_item_id"].startswith("queue-item-")
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
    assert isinstance(state.artifacts.task_plan, TaskPlan)
    assert all(isinstance(task_package, TaskPackage) for task_package in state.artifacts.task_packages)
    assert isinstance(state.artifacts.implementation_package, ImplementationPackage)
    assert isinstance(state.artifacts.validation_package, ValidationPackage)
    assert isinstance(state.artifacts.pull_request, dict)
    assert isinstance(state.artifacts.quality_approval, QualityApproval)


def test_runtime_artifacts_are_sourced_from_prompt_pipeline() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-2A")

    assert state.metadata["artifact_sources"] == {
        "business_brief": "prompt_pipeline",
        "execution_package": "prompt_pipeline",
        "task_plan": "prompt_pipeline",
        "task_packages": "prompt_pipeline",
        "implementation_package": "prompt_pipeline",
        "validation_package": "prompt_pipeline",
        "quality_approval": "prompt_pipeline",
    }
    assert state.metadata["prompt_pipeline"]["pm_business_brief"]["target_artifact"] == (
        "BusinessBrief"
    )
    assert state.metadata["prompt_pipeline"]["po_task_plan"]["target_artifact"] == "TaskPlan"
    assert state.metadata["prompt_pipeline"]["po_task_packages"]["count"] >= 2
    assert state.metadata["prompt_pipeline"]["qa_validation"]["provider_adapter"] == "fake"
    assert state.metadata["business_brief_status"] == "approved"
    assert state.metadata["founder_approved"] is True


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


def test_founder_approval_occurs_before_po_execution_package() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-4B")
    events = state.run.events
    approval_completed_index = next(
        index
        for index, event in enumerate(events)
        if event.step_name == "founder_business_approval"
        and event.metadata["type"] == "STEP_COMPLETED"
        and event.metadata.get("founder_approved") is True
    )
    po_started_index = next(
        index
        for index, event in enumerate(events)
        if event.step_name == "po_execution_package"
        and event.metadata["type"] == "STEP_STARTED"
    )

    assert approval_completed_index < po_started_index


def test_po_task_plan_and_task_packages_occur_before_dev_implementation() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-4BA")
    events = state.run.events
    task_plan_completed_index = next(
        index
        for index, event in enumerate(events)
        if event.step_name == "po_task_plan"
        and event.metadata["type"] == "STEP_COMPLETED"
    )
    task_packages_completed_index = next(
        index
        for index, event in enumerate(events)
        if event.step_name == "po_task_packages"
        and event.metadata["type"] == "STEP_COMPLETED"
    )
    dev_started_index = next(
        index
        for index, event in enumerate(events)
        if event.step_name == "dev_implementation"
        and event.metadata["type"] == "STEP_STARTED"
    )

    assert task_plan_completed_index < task_packages_completed_index < dev_started_index


def test_runtime_registers_founder_conversation_and_approval_events() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-4C")
    conversation_events = [
        event for event in state.run.events if event.step_name == "founder_pm_conversation"
    ]
    approval_events = [
        event for event in state.run.events if event.step_name == "founder_business_approval"
    ]

    assert [event.metadata["type"] for event in conversation_events] == [
        "STEP_STARTED",
        "STEP_COMPLETED",
    ]
    assert [event.metadata["type"] for event in approval_events] == [
        "STEP_STARTED",
        "STEP_COMPLETED",
    ]
    assert approval_events[-1].metadata["founder_approved"] is True
    assert state.run.metadata["founder_pm_conversation"]["thread_id"].startswith("thread-")
    assert state.run.metadata["founder_pm_conversation"]["iteration_count"] == 1
    assert state.run.metadata["founder_pm_conversation"]["message_count"] >= 2
    assert state.run.metadata["founder_business_approval"]["thread_id"].startswith("thread-")


def test_runtime_founder_conversation_creates_pm_response_and_thread_metadata() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-4E")
    thread = state.metadata["conversation_thread"]

    assert thread["thread_id"] == state.metadata["thread_id"]
    assert thread["status"] == "APPROVED"
    assert len(thread["messages"]) >= 2
    assert thread["messages"][0]["author_type"] == "FOUNDER"
    assert any(message["author_type"] == "PM" for message in thread["messages"])


def test_runtime_records_timeline_metadata() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-4F")

    assert state.metadata["timeline_id"].startswith("timeline-")
    assert state.metadata["timeline_event_count"] >= len(state.run.events)
    assert state.metadata["replay_available"] is True
    assert "WORKFLOW" in state.metadata["timeline_sources"]
    assert "SESSION" in state.metadata["timeline_sources"]
    assert any(
        event["event_type"] == "QUEUE_CREATED"
        for event in state.metadata["timeline"]["events"]
    )


def test_dev_consumes_first_task_package_and_qa_validates_task_package() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-4D")

    assert state.artifacts.current_task_package is not None
    assert state.artifacts.current_task_package.task_id == state.metadata["current_queue_task_id"]
    assert state.artifacts.implementation_package is not None
    assert state.artifacts.validation_package is not None
    assert state.artifacts.implementation_package.summary.lower().find("task package") != -1
    assert any(
        "task package" in scenario.lower()
        for scenario in state.artifacts.validation_package.scenarios_validated
    )


def test_runtime_creates_queue_from_task_packages_and_executes_only_first_ready_item() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-4G")
    queue_snapshot = state.metadata["task_queue"]
    task_ids = [task_package.task_id for task_package in state.artifacts.task_packages]
    queued_task_ids = [item["task_id"] for item in queue_snapshot["items"]]
    running_or_finished = {
        item["task_id"]: item["status"]
        for item in queue_snapshot["items"]
    }

    assert queued_task_ids == task_ids
    assert state.metadata["queue_size"] == len(task_ids)
    assert state.metadata["current_queue_item_id"] in {
        item["queue_item_id"] for item in queue_snapshot["items"]
    }
    assert running_or_finished[task_ids[0]] == "COMPLETED"
    assert all(
        running_or_finished[task_id] in {"QUEUED", "BLOCKED", "READY"}
        for task_id in task_ids[1:]
    )


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
