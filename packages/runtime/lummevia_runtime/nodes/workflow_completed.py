from __future__ import annotations

from collections.abc import Callable

from lummevia_core import AgentRole, WorkflowRunStatus
from lummevia_memory import MemoryCategory, MemorySourceType, ProjectMemoryRegistry

from lummevia_runtime.events import complete_step, record_lifecycle_event, start_step
from lummevia_runtime.state import RuntimeState


def workflow_completed_node(
    state: RuntimeState,
    *,
    artifact_publisher: Callable[[str, str, dict], None] | None = None,
) -> RuntimeState:
    step_name = "workflow_completed"
    state = start_step(state, step_name=step_name, role=AgentRole.QA)
    _finalize_public_runtime_context(state)
    state.run.status = WorkflowRunStatus.COMPLETED
    state.metadata["workflow_completed"] = True
    state.metadata["workflow_progress"] = 1.0
    record_lifecycle_event(
        state,
        event_type="WORKFLOW_COMPLETED",
        title="Workflow completed",
        description=f"Workflow run {state.run.run_id} completed after QA pass.",
        metadata={
            "issue_id": state.run.issue_id,
            "handoff_id": state.metadata.get("handoff_id"),
            "completed_tasks": state.metadata.get("completed_tasks", 0),
            "task_count": state.metadata.get("task_count", 0),
        },
    )
    if artifact_publisher is not None:
        artifact_publisher(
            state.run.issue_id,
            "WorkflowCompleted",
            {
                "run_id": state.run.run_id,
                "handoff_id": state.metadata.get("handoff_id"),
                "completed_tasks": state.metadata.get("completed_tasks", 0),
                "task_count": state.metadata.get("task_count", 0),
                "workflow_progress": state.metadata.get("workflow_progress", 1.0),
            },
        )
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.QA,
        metadata={
            "workflow_completed": True,
            "completed_tasks": state.metadata.get("completed_tasks", 0),
            "task_count": state.metadata.get("task_count", 0),
        },
    )


def _finalize_public_runtime_context(state: RuntimeState) -> None:
    current_task_id = (
        state.artifacts.current_task_package.task_id
        if state.artifacts.current_task_package is not None
        else None
    )
    kilo_results = state.metadata.get("kilo_execution_results", {})
    if isinstance(kilo_results, dict):
        state.metadata["kilo_execution_history"] = {
            execution_id: payload
            for execution_id, payload in kilo_results.items()
        }
        if isinstance(current_task_id, str):
            state.metadata["kilo_execution_results"] = {
                execution_id: payload
                for execution_id, payload in kilo_results.items()
                if isinstance(payload, dict)
                and payload.get("task_id") == current_task_id
            }
    if not isinstance(current_task_id, str):
        return
    qa_issue_memories = ProjectMemoryRegistry.default().search_by_category(
        state.run.project,
        MemoryCategory.QA_ISSUE,
    )
    if not qa_issue_memories:
        return
    latest_qa_issue = qa_issue_memories[0]
    if latest_qa_issue.metadata.get("task_id") == current_task_id:
        return
    summary_memory = ProjectMemoryRegistry.default().add_memory(
        project=state.run.project,
        category=MemoryCategory.QA_ISSUE,
        title=f"QA issue summary for {current_task_id}",
        content=(
            f"Workflow {state.run.run_id} completed after prior QA rework. "
            f"Final task context: {current_task_id}."
        ),
        source_type=MemorySourceType.WORKFLOW,
        source_id=state.run.run_id,
        tags=["qa", "issue", current_task_id, state.run.issue_id, "workflow-summary"],
        metadata={
            "run_id": state.run.run_id,
            "issue_id": state.run.issue_id,
            "task_id": current_task_id,
            "workflow_completed": True,
            "summary_only": True,
        },
    )
    state.metadata.setdefault("memory_record_ids", []).append(summary_memory.memory_id)
    state.metadata["memory_records_created"] = len(state.metadata["memory_record_ids"])
