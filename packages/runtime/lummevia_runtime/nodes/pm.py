from __future__ import annotations

from collections.abc import Callable

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
    context_loader: Callable[..., dict | None] | None = None,
    artifact_publisher: Callable[[str, str, dict], None] | None = None,
) -> RuntimeState:
    step_name = "pm_business_brief"
    state = start_step(state, step_name=step_name, role=AgentRole.PM)
    pm_agent = agent or PMAgent()
    project_context = get_project_context(state.run.project)
    external_context = None
    if context_loader is not None:
        external_context = context_loader(
            project=state.run.project,
            role=AgentRole.PM,
            issue_id=state.run.issue_id,
        )
    pipeline_result = pm_agent.execute_prompt_pipeline(
        project=state.run.project,
        issue_id=state.run.issue_id,
        target_artifact="BusinessBrief",
        available_artifacts={
            "founder_input": state.run.metadata.get("founder_input", {}),
            "founder_pm_alignment": state.run.metadata.get("founder_pm_conversation", {}),
            "project_context": project_context,
            "operational_context": external_context.model_dump(mode="json")
            if external_context is not None
            else None,
        },
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "loop_count": state.loop_count,
            "project_memory_count": project_context["project_memory_count"],
            "recent_decision_count": len(project_context["recent_decisions"]),
            "qa_learning_count": len(project_context["qa_learnings"]),
            "has_operational_context": external_context is not None,
        },
    )
    state.artifacts.business_brief = pipeline_result.structured_output
    register_prompt_pipeline_cost(state, step_name=step_name, pipeline_result=pipeline_result)
    state.metadata.setdefault("artifact_sources", {})["business_brief"] = "prompt_pipeline"
    state.metadata.setdefault("prompt_pipeline", {})[step_name] = pipeline_result.metadata
    state.metadata.setdefault("project_context", {})[step_name] = project_context
    if external_context is not None:
        state.metadata.setdefault("operational_context", {})[step_name] = external_context.model_dump(
            mode="json"
        )
    state.metadata["business_brief_status"] = state.artifacts.business_brief.business_brief_status
    state.metadata["founder_approved"] = state.artifacts.business_brief.founder_approved
    state.metadata["conversation_phase"] = state.metadata.get("conversation_phase", "PENDING_APPROVAL")
    state.metadata["brief_version"] = int(state.metadata.get("brief_version", 0) or 0)
    state.run.metadata.setdefault("business_brief_context", {}).update(
        {
            "conversation_thread_id": state.metadata.get("thread_id"),
            "brief_version": state.metadata.get("brief_version", 0),
            "conversation_phase": state.metadata.get("conversation_phase"),
            "pending_questions_count": state.metadata.get("pending_questions_count", 0),
            "iteration_count": state.metadata.get("iteration_count", 0),
        }
    )
    if artifact_publisher is not None:
        artifact_publisher(
            state.run.issue_id,
            "BusinessBrief",
            {
                **state.artifacts.business_brief.model_dump(mode="json"),
                "conversation_thread_id": state.metadata.get("thread_id"),
                "brief_version": state.metadata.get("brief_version", 0),
            },
        )
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.PM,
        metadata={
            "artifact": "BusinessBrief",
            "business_brief_status": state.artifacts.business_brief.business_brief_status,
            "founder_approved": state.artifacts.business_brief.founder_approved,
            "conversation_phase": state.metadata.get("conversation_phase"),
            "brief_version": state.metadata.get("brief_version", 0),
        },
    )
