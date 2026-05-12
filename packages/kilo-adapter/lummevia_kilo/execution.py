from __future__ import annotations

from typing import Any

from lummevia_core import AgentRole, TaskPackage

from lummevia_kilo.modes import KiloExecutionMode, resolve_kilo_mode
from lummevia_kilo.schemas import KiloExecutionRequest, KiloRetryPolicy


def build_kilo_execution_request(
    *,
    run_id: str,
    session_id: str | None = None,
    role: AgentRole,
    project: str,
    repo_path: str,
    task_package: TaskPackage,
    metadata: dict[str, Any] | None = None,
    mode: KiloExecutionMode | None = None,
    retry_policy: KiloRetryPolicy | None = None,
) -> KiloExecutionRequest:
    request_metadata = metadata or {}
    return KiloExecutionRequest(
        run_id=run_id,
        session_id=session_id,
        role=role,
        mode=mode or resolve_kilo_mode(role),
        project=project,
        repo_path=repo_path,
        task_package=task_package,
        metadata=request_metadata,
        retry_policy=retry_policy
        or KiloRetryPolicy(max_attempts=int(request_metadata.get("max_attempts", 1))),
    )


def build_planning_task_package(
    *,
    issue_id: str,
    project: str,
    task_id: str,
    title: str,
    objective: str,
    prompt: str,
    expected_artifacts: list[str],
    context_refs: list[str] | None = None,
    constraints: list[str] | None = None,
) -> TaskPackage:
    return TaskPackage(
        task_id=task_id,
        issue_id=issue_id,
        project=project,
        title=title,
        objective=objective,
        target_repo=project,
        context_refs=context_refs or [],
        acceptance_criteria=[
            "Preserve the documented workflow decomposition.",
            "Keep the adapter boundary fake and deterministic.",
        ],
        constraints=constraints
        or [
            "Do not execute the real Kilo CLI.",
            "Do not mutate the filesystem or git state.",
        ],
        prompt=prompt,
        expected_artifacts=expected_artifacts,
        status="planned",
    )
