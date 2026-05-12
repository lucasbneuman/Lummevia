from fastapi.testclient import TestClient

from lummevia_core import AgentRole, ExecutionPackage, TaskPlan, WorkflowRun, WorkflowRunStatus
from lummevia_kilo import resolve_kilo_mode
from lummevia_resources import (
    ResourceLockStatus,
    ResourceRegistry,
    ResourceType,
    WorkspaceAllocator,
    WorkspaceStatus,
)
from lummevia_runtime.nodes.dev import dev_implementation_node
from lummevia_runtime.nodes.po import po_task_packages_node
from lummevia_runtime.nodes.qa import qa_validation_node
from lummevia_runtime.state import RuntimeArtifacts, RuntimeState
from lummevia_sessions import SessionRegistry, SessionStatus
from main import app


client = TestClient(app)


def test_resource_registry_acquires_blocks_duplicates_and_releases() -> None:
    registry = ResourceRegistry()
    first = registry.acquire_lock(
        resource_type=ResourceType.REPO,
        resource_id="lummevia-os",
        owner_id="queue-item-1",
        owner_type="TaskQueueItem",
    )

    assert first.status == ResourceLockStatus.ACQUIRED
    assert registry.get_lock(first.lock_id) == first
    assert registry.list_active_locks() == [first]

    try:
        registry.acquire_lock(
            resource_type=ResourceType.REPO,
            resource_id="lummevia-os",
            owner_id="queue-item-2",
            owner_type="TaskQueueItem",
        )
    except ValueError as exc:
        assert "active lock" in str(exc)
    else:
        raise AssertionError("Expected duplicate active lock to be blocked.")

    released = registry.release_lock(first.lock_id)

    assert released.status == ResourceLockStatus.RELEASED
    assert released.released_at is not None
    assert registry.list_active_locks() == []


def test_workspace_allocator_is_deterministic_and_safe() -> None:
    from lummevia_core import TaskPackage
    from lummevia_queue import TaskQueueItem

    task_package = TaskPackage(
        task_id="OS-900-T1",
        issue_id="OS-900",
        project="lummevia-os",
        title="Prepare workspace contracts",
        objective="Allocate a fake workspace.",
        target_repo="lummevia-os",
        context_refs=["docs/03-workflows/loop-desarrollo.md"],
        acceptance_criteria=["No real worktree is created"],
        constraints=["No git worktree", "No subprocess"],
        prompt="Allocate a fake workspace.",
        expected_artifacts=["ImplementationPackage"],
        status="planned",
    )
    queue_item = TaskQueueItem.model_validate(
        {
            "queue_item_id": "queue-item-fixed-001",
            "task_id": "OS-900-T1",
            "project": "lummevia-os",
            "issue_id": "OS-900",
            "assigned_role": AgentRole.DEV,
            "mode": "CODE",
        }
    )
    allocator = WorkspaceAllocator(workspace_root="/simulated/root")

    workspace = allocator.allocate_workspace(task_package, queue_item)

    assert workspace.workspace_id.startswith("workspace-")
    assert workspace.branch_name == "lummevia/lummevia-os/os-900-t1-001"
    assert workspace.worktree_path == f"/simulated/root/lummevia-os/{workspace.workspace_id}"
    assert workspace.metadata["simulated"] is True
    assert len(workspace.metadata["lock_ids"]) == 3
    assert allocator.registry.list_active_locks()


def test_runtime_assigns_workspace_and_session_metadata_to_active_task() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-901"},
    )
    assert runtime_response.status_code == 200
    state = runtime_response.json()

    assert state["metadata"]["workspace_id"].startswith("workspace-")
    assert state["metadata"]["branch_name"].startswith("lummevia/")
    assert state["metadata"]["resource_locks_count"] == 3
    assert state["metadata"]["workspace_status"] == "RELEASED"

    queue_snapshot = state["metadata"]["task_queue"]
    running_or_completed = next(
        item
        for item in queue_snapshot["items"]
        if item["queue_item_id"] == state["metadata"]["current_queue_item_id"]
    )
    assert running_or_completed["metadata"]["workspace_id"].startswith("workspace-")
    assert running_or_completed["metadata"]["branch_name"].startswith("lummevia/")
    assert "worktree_path" in running_or_completed["metadata"]
    assert running_or_completed["metadata"]["lock_ids"]

    session = SessionRegistry.default().get_session(state["metadata"]["current_session_id"])
    assert session is not None
    assert session.workspace_id == state["metadata"]["workspace_id"]
    assert session.branch_name == state["metadata"]["branch_name"]
    assert session.worktree_path == state["metadata"]["worktree_path"]
    assert session.lock_ids == state["metadata"]["lock_ids"]
    assert session.status == SessionStatus.COMPLETED

    task_bound_results = [
        result
        for result in state["metadata"]["kilo_execution_results"].values()
        if result["metadata"].get("workspace_id")
    ]
    assert task_bound_results
    assert all(result["metadata"]["workspace_id"] == state["metadata"]["workspace_id"] for result in task_bound_results)
    assert all(result["metadata"]["branch_name"] == state["metadata"]["branch_name"] for result in task_bound_results)
    assert all(result["metadata"]["worktree_path"] == state["metadata"]["worktree_path"] for result in task_bound_results)
    assert all(result["metadata"]["lock_ids"] == state["metadata"]["lock_ids"] for result in task_bound_results)


def test_qa_fail_keeps_workspace_active_and_session_waiting_review() -> None:
    state = RuntimeState(
        run=WorkflowRun(
            workflow_name="development_loop",
            project="lummevia-os",
            issue_id="OS-902",
            status=WorkflowRunStatus.RUNNING,
            current_step="po_task_packages",
            events=[],
            metadata={},
        ),
        artifacts=RuntimeArtifacts(
            execution_package=ExecutionPackage(
                issue_id="OS-902",
                project="lummevia-os",
                technical_story="Add fake workspace isolation.",
                acceptance_criteria=["Workspace metadata is propagated"],
                edge_cases=["QA fail keeps workspace"],
                testing_scenarios=["Direct node execution"],
                architecture_decisions=["No real worktrees yet"],
                task_checklist=["Create locks", "Create workspace metadata"],
                dev_prompts=["Implement fake workspace contracts."],
            ),
            task_plan=TaskPlan(
                issue_id="OS-902",
                project="lummevia-os",
                workstreams=["runtime_state_and_contracts"],
                task_packages=["OS-902-T1"],
                sequencing_notes=["Use one task only."],
                risks=["Future parallel execution may require stricter limits."],
            ),
        ),
        metadata={
            "workflow": "development_loop",
            "repo_path": "C:/repo/lummevia-os",
        },
        max_loop_count=1,
    )

    state = po_task_packages_node(state)
    state = dev_implementation_node(state)
    state = qa_validation_node(state)

    workspace = ResourceRegistry.default().get_workspace(state.metadata["workspace_id"])
    assert workspace is not None
    assert workspace.status == WorkspaceStatus.ACTIVE
    assert state.metadata["workspace_status"] == "ACTIVE"
    assert SessionRegistry.default().get_session(state.metadata["current_session_id"]).status == SessionStatus.WAITING_REVIEW
    assert len(ResourceRegistry.default().list_active_locks()) == 3


def test_resource_endpoints_list_locks_and_workspaces() -> None:
    runtime_response = client.post(
        "/runtime/development/run",
        json={"project": "lummevia-os", "issue_id": "OS-903"},
    )
    assert runtime_response.status_code == 200
    workspace_id = runtime_response.json()["metadata"]["workspace_id"]

    locks_response = client.get("/resources/locks")
    workspaces_response = client.get("/resources/workspaces")
    workspace_response = client.get(f"/resources/workspaces/{workspace_id}")

    assert locks_response.status_code == 200
    assert workspaces_response.status_code == 200
    assert workspace_response.status_code == 200
    assert len(locks_response.json()) >= 3
    assert any(workspace["workspace_id"] == workspace_id for workspace in workspaces_response.json())
    assert workspace_response.json()["workspace_id"] == workspace_id
    assert workspace_response.json()["status"] == "RELEASED"
