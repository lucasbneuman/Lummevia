from __future__ import annotations

from lummevia_core import AgentRole
from lummevia_agents import DevAgent

from lummevia_runtime.events import complete_step, start_step
from lummevia_runtime.state import RuntimeState


def dev_implementation_node(
    state: RuntimeState,
    *,
    agent: DevAgent | None = None,
) -> RuntimeState:
    step_name = "dev_implementation"
    state = start_step(state, step_name=step_name, role=AgentRole.DEV)
    dev_agent = agent or DevAgent()
    pipeline_result = dev_agent.execute_prompt_pipeline(
        project=state.run.project,
        issue_id=state.run.issue_id,
        target_artifact="ImplementationPackage",
        available_artifacts={
            "execution_package": state.artifacts.execution_package,
            "validation_package": state.artifacts.validation_package,
        },
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "loop_count": state.loop_count,
            "implementation_revision": state.loop_count + 1,
        },
    )
    state.artifacts.implementation_package = pipeline_result.structured_output
    state.metadata.setdefault("artifact_sources", {})["implementation_package"] = (
        "prompt_pipeline"
    )
    state.metadata.setdefault("prompt_pipeline", {})[step_name] = pipeline_result.metadata
    state.metadata["implementation_revision"] = state.loop_count + 1
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.DEV,
        metadata={
            "artifact": "ImplementationPackage",
            "rework": state.loop_count > 0,
        },
    )
