from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.routes.runtime import _build_kilo_runtime_settings
from lummevia_core import AgentRole, TaskPackage
from lummevia_kilo import (
    KiloExecutionClient,
    KiloExecutionMode,
    KiloExecutionRequest,
    KiloExecutionResult,
)


router = APIRouter(prefix="/kilo", tags=["kilo"])
sandbox_client = KiloExecutionClient(settings=_build_kilo_runtime_settings())


class SandboxRunRequest(BaseModel):
    project: str
    repo_path: str
    task_id: str
    prompt: str
    mode: KiloExecutionMode


@router.post("/sandbox/run", response_model=KiloExecutionResult)
def run_kilo_sandbox(request: SandboxRunRequest) -> KiloExecutionResult:
    task_package = TaskPackage(
        task_id=request.task_id,
        issue_id=request.task_id.split("-T")[0],
        project=request.project,
        title=f"Sandbox execution for {request.task_id}",
        objective="Run a controlled Kilo sandbox diagnostic.",
        target_repo=request.project,
        context_refs=["docs/03-workflows/loop-desarrollo.md"],
        acceptance_criteria=[
            "Do not touch the original repository.",
            "Do not push, merge, or open PRs.",
        ],
        constraints=[
            "No productive repository mutation.",
            "No external arbitrary command execution.",
        ],
        prompt=request.prompt,
        expected_artifacts=["SandboxExecutionReport"],
        status="planned",
    )
    kilo_request = KiloExecutionRequest(
        run_id=f"sandbox-{request.task_id.casefold()}",
        role=AgentRole.DEV,
        mode=request.mode,
        project=request.project,
        repo_path=request.repo_path,
        task_package=task_package,
        metadata={
            "step_name": "sandbox_run",
            "diagnostic_endpoint": True,
            "persist_workflow": False,
        },
    )
    return sandbox_client.execute(kilo_request)
