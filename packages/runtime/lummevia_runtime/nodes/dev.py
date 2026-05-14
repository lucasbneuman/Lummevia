from __future__ import annotations

from lummevia_core import AgentRole
from lummevia_agents import DevAgent
from lummevia_kilo import KiloExecutionClient, resolve_kilo_mode
from lummevia_sessions import SessionStatus

from lummevia_runtime.economics import register_prompt_pipeline_cost
from lummevia_runtime.events import complete_step, start_step
from lummevia_runtime.kilo import execute_kilo_step
from lummevia_runtime.sessions import add_session_output, update_task_execution_session
from lummevia_runtime.state import RuntimeState


def dev_implementation_node(
    state: RuntimeState,
    *,
    agent: DevAgent | None = None,
    kilo_client: KiloExecutionClient | None = None,
) -> RuntimeState:
    step_name = "dev_implementation"
    task_package = state.artifacts.current_task_package
    if task_package is None:
        raise ValueError("TaskPackage must exist before DEV implementation.")

    state = start_step(state, step_name=step_name, role=AgentRole.DEV)
    update_task_execution_session(
        state,
        status=SessionStatus.RUNNING,
        role=AgentRole.DEV,
        mode=resolve_kilo_mode(AgentRole.DEV),
        metadata={"current_step": step_name},
    )
    state.artifacts.current_task_package = task_package.model_copy(
        update={"status": "in_progress"}
    )
    if state.artifacts.task_packages:
        state.artifacts.task_packages = [
            (
                state.artifacts.current_task_package
                if existing.task_id == state.artifacts.current_task_package.task_id
                else existing
            )
            for existing in state.artifacts.task_packages
        ]
    kilo_execution = execute_kilo_step(
        state,
        step_name=step_name,
        role=AgentRole.DEV,
        task_package=state.artifacts.current_task_package,
        client=kilo_client or KiloExecutionClient(),
        metadata={"target_artifact": "ImplementationPackage"},
    )
    dev_agent = agent or DevAgent()
    pipeline_result = dev_agent.execute_prompt_pipeline(
        project=state.run.project,
        issue_id=state.run.issue_id,
        target_artifact="ImplementationPackage",
        available_artifacts={
            "execution_package": state.artifacts.execution_package,
            "task_plan": state.artifacts.task_plan,
            "task_package": task_package,
            "validation_package": state.artifacts.validation_package,
        },
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "loop_count": state.loop_count,
            "implementation_revision": state.loop_count + 1,
            "task_id": task_package.task_id,
        },
    )
    state.artifacts.implementation_package = pipeline_result.structured_output
    register_prompt_pipeline_cost(state, step_name=step_name, pipeline_result=pipeline_result)
    state.metadata.setdefault("artifact_sources", {})["implementation_package"] = (
        "prompt_pipeline"
    )
    state.metadata.setdefault("kilo", {})[step_name] = kilo_execution
    state.metadata.setdefault("prompt_pipeline", {})[step_name] = pipeline_result.metadata
    state.metadata["implementation_revision"] = state.loop_count + 1
    add_session_output(
        state,
        output_type="implementation_package",
        content=state.artifacts.implementation_package.summary,
        metadata={
            "task_id": task_package.task_id,
            "rework": state.loop_count > 0,
            "implementation_revision": state.loop_count + 1,
        },
    )
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.DEV,
        metadata={
            "artifact": "ImplementationPackage",
            "rework": state.loop_count > 0,
            "task_id": task_package.task_id,
        },
    )
