from __future__ import annotations

from lummevia_core import AgentRole, ValidationStatus
from lummevia_agents import QAAgent

from lummevia_runtime.events import complete_step, log_loop_reentered, start_step
from lummevia_runtime.state import RuntimeState


def qa_validation_node(
    state: RuntimeState,
    *,
    agent: QAAgent | None = None,
) -> RuntimeState:
    step_name = "qa_validation"
    task_package = state.artifacts.current_task_package
    if task_package is None:
        raise ValueError("TaskPackage must exist before QA validation.")

    state = start_step(state, step_name=step_name, role=AgentRole.QA)

    qa_agent = agent or QAAgent()
    pipeline_result = qa_agent.execute_prompt_pipeline(
        project=state.run.project,
        issue_id=state.run.issue_id,
        target_artifact="ValidationPackage",
        available_artifacts={
            "execution_package": state.artifacts.execution_package,
            "task_package": task_package,
            "implementation_package": state.artifacts.implementation_package,
        },
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "loop_count": state.loop_count,
            "task_id": task_package.task_id,
        },
    )
    state.artifacts.validation_package = pipeline_result.structured_output
    updated_task_status = (
        "validated"
        if state.artifacts.validation_package.status == ValidationStatus.PASSED
        else "in_progress"
    )
    state.artifacts.current_task_package = task_package.model_copy(
        update={"status": updated_task_status}
    )
    if state.artifacts.task_packages:
        state.artifacts.task_packages[0] = state.artifacts.current_task_package
    state.metadata.setdefault("artifact_sources", {})["validation_package"] = (
        "prompt_pipeline"
    )
    state.metadata.setdefault("prompt_pipeline", {})[step_name] = pipeline_result.metadata
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.QA,
        metadata={
            "artifact": "ValidationPackage",
            "task_id": task_package.task_id,
            "validation_status": state.artifacts.validation_package.status.value,
        },
    )


def dev_qa_iteration_node(state: RuntimeState) -> RuntimeState:
    step_name = "dev_qa_iteration"
    state = start_step(state, step_name=step_name, role=AgentRole.QA)
    state.loop_count += 1
    state.metadata["loop_reentered"] = True
    state = log_loop_reentered(state, step_name=step_name, role=AgentRole.QA)
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.QA,
        metadata={"next_step": "dev_implementation"},
    )
