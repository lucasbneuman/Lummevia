from __future__ import annotations

from lummevia_core import AgentRole, WorkflowRunStatus
from lummevia_agents import POAgent

from lummevia_runtime.events import complete_step, start_step
from lummevia_runtime.state import RuntimeState


def po_execution_package_node(
    state: RuntimeState,
    *,
    agent: POAgent | None = None,
) -> RuntimeState:
    step_name = "po_execution_package"
    business_brief = state.artifacts.business_brief
    if business_brief is None:
        raise ValueError("BusinessBrief must exist before PO execution package.")
    if not business_brief.founder_approved or business_brief.business_brief_status != "approved":
        raise ValueError("PO execution package requires an approved BusinessBrief.")

    state = start_step(state, step_name=step_name, role=AgentRole.PO)
    po_agent = agent or POAgent()
    pipeline_result = po_agent.execute_prompt_pipeline(
        project=state.run.project,
        issue_id=state.run.issue_id,
        target_artifact="ExecutionPackage",
        available_artifacts={
            "business_brief": business_brief,
        },
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "loop_count": state.loop_count,
            "founder_approved": business_brief.founder_approved,
            "business_brief_status": business_brief.business_brief_status,
        },
    )
    state.artifacts.execution_package = pipeline_result.structured_output
    state.metadata.setdefault("artifact_sources", {})["execution_package"] = (
        "prompt_pipeline"
    )
    state.metadata.setdefault("prompt_pipeline", {})[step_name] = pipeline_result.metadata
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.PO,
        metadata={
            "artifact": "ExecutionPackage",
            "business_brief_status": business_brief.business_brief_status,
            "founder_approved": business_brief.founder_approved,
        },
    )


def po_final_validation_node(state: RuntimeState) -> RuntimeState:
    step_name = "po_final_validation"
    state = start_step(state, step_name=step_name, role=AgentRole.PO)
    state.artifacts.final_validation = {
        "issue_id": state.run.issue_id,
        "project": state.run.project,
        "approved": True,
        "summary": "Functional validation completed on simulated runtime output.",
    }
    state.run.status = WorkflowRunStatus.COMPLETED
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.PO,
        metadata={"artifact": "final_validation"},
    )
