from __future__ import annotations

from typing import Any

from lummevia_core import AgentRole, TaskPackage
from lummevia_kilo import (
    KiloExecutionClient,
    build_kilo_execution_request,
    build_planning_task_package,
    resolve_kilo_mode,
)

from lummevia_runtime.state import RuntimeState


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
    request = build_kilo_execution_request(
        run_id=state.run.run_id,
        role=role,
        project=state.run.project,
        repo_path=str(state.metadata.get("repo_path", state.run.project)),
        task_package=task_package,
        metadata={
            "step_name": step_name,
            "task_id": task_package.task_id,
            "loop_count": state.loop_count,
            **(metadata or {}),
        },
    )
    result = client.execute(request)
    record = {
        "execution_id": result.execution_id,
        "role": role.value,
        "mode": mode.value,
        "task_id": task_package.task_id,
        "status": result.status,
    }
    state.kilo_executions.append(record)
    state.metadata.setdefault("kilo_executions", []).append(record)
    state.metadata.setdefault("kilo_execution_results", {})[result.execution_id] = (
        result.model_dump(mode="json")
    )
    state.metadata.setdefault("kilo_execution_by_step", {})[step_name] = {
        "execution_id": result.execution_id,
        "role": role.value,
        "kilo_mode": mode.value,
        "task_id": task_package.task_id,
        "status": result.status,
    }
    return result.model_dump(mode="json")
