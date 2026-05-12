from __future__ import annotations

from typing import Any

from lummevia_core import AgentRole, TaskPackage
from lummevia_kilo import (
    KiloExecutionClient,
    KiloExecutionRecord,
    KiloExecutionResult,
    build_kilo_execution_request,
    build_planning_task_package,
    resolve_kilo_mode,
)

from lummevia_runtime.sessions import record_kilo_execution_for_session
from lummevia_runtime.state import RuntimeState
from lummevia_runtime.queue import build_queue_metadata_for_kilo


def build_runtime_planning_task_package(
    *,
    state: RuntimeState,
    task_id: str,
    title: str,
    objective: str,
    prompt: str,
    expected_artifacts: list[str],
    context_refs: list[str] | None = None,
) -> TaskPackage:
    return build_planning_task_package(
        issue_id=state.run.issue_id,
        project=state.run.project,
        task_id=task_id,
        title=title,
        objective=objective,
        prompt=prompt,
        expected_artifacts=expected_artifacts,
        context_refs=context_refs,
    )


def execute_kilo_step(
    state: RuntimeState,
    *,
    step_name: str,
    role: AgentRole,
    task_package: TaskPackage,
    client: KiloExecutionClient,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mode = resolve_kilo_mode(role)
    session_id = state.metadata.get("current_session_id")
    request = build_kilo_execution_request(
        run_id=state.run.run_id,
        session_id=session_id if isinstance(session_id, str) else None,
        role=role,
        project=state.run.project,
        repo_path=str(state.metadata.get("repo_path", state.run.project)),
        task_package=task_package,
        metadata={
            "step_name": step_name,
            "task_id": task_package.task_id,
            "loop_count": state.loop_count,
            **build_queue_metadata_for_kilo(state, task_package=task_package),
            **(metadata or {}),
        },
    )
    result = client.execute(request)
    record = KiloExecutionRecord(
        execution_id=result.execution_id,
        session_id=request.session_id,
        role=role,
        mode=mode,
        task_id=task_package.task_id,
        status=result.status,
        final_status=result.final_status,
        retry_count=result.retry_count,
        attempts=result.attempts,
        lifecycle=result.lifecycle,
        error=result.error,
    )
    state.kilo_executions.append(record)
    state.metadata.setdefault("kilo_executions", []).append(record.model_dump(mode="json"))
    state.metadata.setdefault("kilo_execution_results", {})[result.execution_id] = (
        result.model_dump(mode="json")
    )
    state.metadata.setdefault("kilo_execution_by_step", {})[step_name] = {
        "execution_id": result.execution_id,
        "session_id": request.session_id,
        "role": role.value,
        "kilo_mode": mode.value,
        "task_id": task_package.task_id,
        "queue_id": result.metadata.get("queue_id"),
        "queue_item_id": result.metadata.get("queue_item_id"),
        "workspace_id": result.metadata.get("workspace_id"),
        "branch_name": result.metadata.get("branch_name"),
        "worktree_path": result.metadata.get("worktree_path"),
        "lock_ids": result.metadata.get("lock_ids", []),
        "workspace_status": result.metadata.get("workspace_status"),
        "kilo_status": result.status.value,
        "attempts_count": len(result.attempts),
        "attempts": [attempt.model_dump(mode="json") for attempt in result.attempts],
        "retry_count": result.retry_count,
        "final_status": result.final_status.value,
        "status": result.status.value,
        "error": result.error,
    }
    if request.session_id is not None:
        record_kilo_execution_for_session(
            state,
            step_name=step_name,
            role=role,
            mode=mode,
            result=KiloExecutionResult.model_validate(result.model_dump(mode="json")),
        )
    return result.model_dump(mode="json")
