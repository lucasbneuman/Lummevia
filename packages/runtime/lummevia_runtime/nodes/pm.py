from __future__ import annotations

from lummevia_core import AgentRole
from lummevia_agents import PMAgent
from lummevia_memory import get_project_context

from lummevia_runtime.economics import register_prompt_pipeline_cost
from lummevia_runtime.events import complete_step, start_step
from lummevia_runtime.state import RuntimeState


def pm_business_brief_node(
    state: RuntimeState,
    *,
    agent: PMAgent | None = None,
) -> RuntimeState:
    step_name = "pm_business_brief"
    state = start_step(state, step_name=step_name, role=AgentRole.PM)
    pm_agent = agent or PMAgent()
    project_context = get_project_context(state.run.project)
    pipeline_result = pm_agent.execute_prompt_pipeline(
        project=state.run.project,
        issue_id=state.run.issue_id,
        target_artifact="BusinessBrief",
        available_artifacts={
            "founder_input": state.run.metadata.get("founder_input", {}),
            "founder_pm_alignment": state.run.metadata.get("founder_pm_conversation", {}),
            "project_context": project_context,
        },
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "loop_count": state.loop_count,
            "project_memory_count": project_context["project_memory_count"],
            "recent_decision_count": len(project_context["recent_decisions"]),
            "qa_learning_count": len(project_context["qa_learnings"]),
        },
    )
    state.artifacts.business_brief = pipeline_result.structured_output
    register_prompt_pipeline_cost(state, step_name=step_name, pipeline_result=pipeline_result)
    state.metadata.setdefault("artifact_sources", {})["business_brief"] = "prompt_pipeline"
    state.metadata.setdefault("prompt_pipeline", {})[step_name] = pipeline_result.metadata
    state.metadata.setdefault("project_context", {})[step_name] = project_context
    state.metadata["business_brief_status"] = state.artifacts.business_brief.business_brief_status
    state.metadata["founder_approved"] = state.artifacts.business_brief.founder_approved
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.PM,
        metadata={
            "artifact": "BusinessBrief",
            "business_brief_status": state.artifacts.business_brief.business_brief_status,
            "founder_approved": state.artifacts.business_brief.founder_approved,
        },
    )
