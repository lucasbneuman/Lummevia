from __future__ import annotations

from collections.abc import Callable

from lummevia_core import AgentRole
from lummevia_agents import QCAgent

from lummevia_runtime.economics import register_prompt_pipeline_cost
from lummevia_runtime.events import complete_step, start_step
from lummevia_runtime.state import RuntimeState


def qc_quality_approval_node(
    state: RuntimeState,
    *,
    agent: QCAgent | None = None,
    artifact_publisher: Callable[[str, str, dict], None] | None = None,
) -> RuntimeState:
    step_name = "qc_quality_approval"
    state = start_step(state, step_name=step_name, role=AgentRole.QC)
    qc_agent = agent or QCAgent()
    pull_request = state.artifacts.pull_request or {}
    pipeline_result = qc_agent.execute_prompt_pipeline(
        project=state.run.project,
        issue_id=state.run.issue_id,
        target_artifact="QualityApproval",
        available_artifacts={
            "pull_request": pull_request,
            "validation_package": state.artifacts.validation_package,
            "implementation_package": state.artifacts.implementation_package,
        },
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "loop_count": state.loop_count,
        },
    )
    state.artifacts.quality_approval = pipeline_result.structured_output
    register_prompt_pipeline_cost(state, step_name=step_name, pipeline_result=pipeline_result)
    state.metadata.setdefault("artifact_sources", {})["quality_approval"] = (
        "prompt_pipeline"
    )
    state.metadata.setdefault("prompt_pipeline", {})[step_name] = pipeline_result.metadata
    if artifact_publisher is not None:
        artifact_publisher(
            state.run.issue_id,
            "QualityApproval",
            state.artifacts.quality_approval.model_dump(mode="json"),
        )
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.QC,
        metadata={
            "artifact": "QualityApproval",
            "pull_request_available": bool(pull_request),
        },
    )
