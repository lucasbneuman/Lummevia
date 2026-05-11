from __future__ import annotations

from lummevia_core import AgentRole
from lummevia_agents import QAAgent

from lummevia_runtime.events import complete_step, log_loop_reentered, start_step
from lummevia_runtime.state import RuntimeState


def qa_validation_node(
    state: RuntimeState,
    *,
    agent: QAAgent | None = None,
) -> RuntimeState:
    step_name = "qa_validation"
    state = start_step(state, step_name=step_name, role=AgentRole.QA)

    qa_agent = agent or QAAgent()
    pipeline_result = qa_agent.execute_prompt_pipeline(
        project=state.run.project,
        issue_id=state.run.issue_id,
        target_artifact="ValidationPackage",
        available_artifacts={
            "execution_package": state.artifacts.execution_package,
            "implementation_package": state.artifacts.implementation_package,
        },
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "loop_count": state.loop_count,
        },
    )
    state.artifacts.validation_package = pipeline_result.structured_output
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
