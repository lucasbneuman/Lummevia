from lummevia_core import AgentRole, TaskPackage
from lummevia_runtime import DevelopmentRuntime
from lummevia_kilo import (
    KiloExecutionClient,
    KiloExecutionMode,
    KiloExecutionRequest,
    resolve_kilo_mode,
)


def _build_task_package(task_id: str = "OS-500-T1") -> TaskPackage:
    return TaskPackage(
        task_id=task_id,
        issue_id="OS-500",
        project="lummevia-os",
        title="Implement Kilo adapter skeleton",
        objective="Prepare a fake Kilo execution boundary.",
        target_repo="lummevia-os",
        context_refs=[
            "docs/03-workflows/loop-desarrollo.md",
            "packages/runtime/lummevia_runtime/graph.py",
        ],
        acceptance_criteria=[
            "Kilo execution is simulated",
            "Runtime remains deterministic",
        ],
        constraints=[
            "Do not execute real CLI commands",
            "Do not mutate git state",
        ],
        prompt="Execute this TaskPackage through the fake Kilo adapter.",
        expected_artifacts=["ImplementationPackage"],
        status="planned",
    )


def test_kilo_execution_client_returns_valid_deterministic_result() -> None:
    client = KiloExecutionClient()
    request = KiloExecutionRequest(
        run_id="run-500",
        role=AgentRole.DEV,
        mode=KiloExecutionMode.CODE,
        project="lummevia-os",
        repo_path="C:/repo/lummevia-os",
        task_package=_build_task_package(),
        metadata={"step_name": "dev_implementation"},
    )

    first = client.execute(request)
    second = client.execute(request)

    assert first == second
    assert first.execution_id.startswith("kilo-")
    assert first.status == "completed"
    assert first.summary
    assert first.logs
    assert first.duration_ms >= 0
    assert first.generated_artifacts
    assert first.metadata["mode"] == KiloExecutionMode.CODE.value
    assert first.metadata["role"] == AgentRole.DEV.value
    assert first.metadata["task_id"] == "OS-500-T1"


def test_role_to_kilo_mode_mapping_matches_runtime_contract() -> None:
    assert resolve_kilo_mode(AgentRole.PO) == KiloExecutionMode.PLAN
    assert resolve_kilo_mode(AgentRole.DEV) == KiloExecutionMode.CODE
    assert resolve_kilo_mode(AgentRole.QA) == KiloExecutionMode.DEBUG


def test_runtime_registers_kilo_executions_for_po_dev_and_qa() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-501")

    executions = state.metadata["kilo_executions"]

    assert executions
    assert any(
        execution["role"] == AgentRole.PO.value
        and execution["mode"] == KiloExecutionMode.PLAN.value
        for execution in executions
    )
    assert any(
        execution["role"] == AgentRole.DEV.value
        and execution["mode"] == KiloExecutionMode.CODE.value
        for execution in executions
    )
    assert any(
        execution["role"] == AgentRole.QA.value
        and execution["mode"] == KiloExecutionMode.DEBUG.value
        for execution in executions
    )

    first_task_id = state.artifacts.current_task_package.task_id
    assert any(
        execution["task_id"] == first_task_id and execution["status"] == "completed"
        for execution in executions
    )
