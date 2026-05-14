from __future__ import annotations

from lummevia_core import AgentRole, WorkflowRunStatus
from lummevia_agents import POAgent
from lummevia_kilo import KiloExecutionClient, resolve_kilo_mode

from lummevia_runtime.economics import register_prompt_pipeline_cost
from lummevia_runtime.events import complete_step, start_step
from lummevia_runtime.kilo import build_runtime_planning_task_package, execute_kilo_step
from lummevia_runtime.queue import initialize_task_queue
from lummevia_runtime.sessions import add_session_output, create_task_execution_session
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
    register_prompt_pipeline_cost(state, step_name=step_name, pipeline_result=pipeline_result)
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


def po_task_plan_node(
    state: RuntimeState,
    *,
    agent: POAgent | None = None,
    kilo_client: KiloExecutionClient | None = None,
) -> RuntimeState:
    step_name = "po_task_plan"
    execution_package = state.artifacts.execution_package
    if execution_package is None:
        raise ValueError("ExecutionPackage must exist before PO task planning.")

    state = start_step(state, step_name=step_name, role=AgentRole.PO)
    po_agent = agent or POAgent()
    pipeline_result = po_agent.execute_prompt_pipeline(
        project=state.run.project,
        issue_id=state.run.issue_id,
        target_artifact="TaskPlan",
        available_artifacts={
            "execution_package": execution_package,
        },
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "loop_count": state.loop_count,
        },
    )
    state.artifacts.task_plan = pipeline_result.structured_output
    register_prompt_pipeline_cost(state, step_name=step_name, pipeline_result=pipeline_result)
    planning_task_package = build_runtime_planning_task_package(
        state=state,
        task_id=f"{state.run.issue_id}-PLAN",
        title="Plan execution sequencing",
        objective="Translate the execution package into a sequenced TaskPlan.",
        prompt="Produce a simulated TaskPlan boundary for the fake Kilo PLAN mode.",
        expected_artifacts=["TaskPlan"],
        context_refs=[
            "docs/03-workflows/loop-desarrollo.md",
            "docs/06-decisiones/0005-po-task-decomposition-flow.md",
        ],
    )
    kilo_execution = execute_kilo_step(
        state,
        step_name=step_name,
        role=AgentRole.PO,
        task_package=planning_task_package,
        client=kilo_client or KiloExecutionClient(),
        metadata={"target_artifact": "TaskPlan"},
    )
    state.metadata.setdefault("artifact_sources", {})["task_plan"] = "prompt_pipeline"
    state.metadata.setdefault("kilo", {})[step_name] = kilo_execution
    state.metadata.setdefault("prompt_pipeline", {})[step_name] = pipeline_result.metadata
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.PO,
        metadata={
            "artifact": "TaskPlan",
            "task_package_count": len(state.artifacts.task_plan.task_packages),
        },
    )


def po_task_packages_node(
    state: RuntimeState,
    *,
    agent: POAgent | None = None,
    kilo_client: KiloExecutionClient | None = None,
) -> RuntimeState:
    step_name = "po_task_packages"
    task_plan = state.artifacts.task_plan
    if task_plan is None:
        raise ValueError("TaskPlan must exist before PO task packages.")

    state = start_step(state, step_name=step_name, role=AgentRole.PO)
    po_agent = agent or POAgent()
    task_packages = []
    for task_index, task_id in enumerate(task_plan.task_packages):
        pipeline_result = po_agent.execute_prompt_pipeline(
            project=state.run.project,
            issue_id=state.run.issue_id,
            target_artifact="TaskPackage",
            available_artifacts={
                "execution_package": state.artifacts.execution_package,
                "task_plan": task_plan,
            },
            metadata={
                "run_id": state.run.run_id,
                "step_name": step_name,
                "loop_count": state.loop_count,
                "task_id": task_id,
                "task_index": task_index,
            },
        )
        task_packages.append(pipeline_result.structured_output)
        register_prompt_pipeline_cost(state, step_name=step_name, pipeline_result=pipeline_result)
    state.artifacts.task_packages = task_packages
    initialize_task_queue(state, task_packages=task_packages)
    current_task_id = state.metadata.get("current_queue_task_id")
    state.artifacts.current_task_package = next(
        (
            task_package
            for task_package in task_packages
            if task_package.task_id == current_task_id
        ),
        task_packages[0] if task_packages else None,
    )
    if state.artifacts.current_task_package is not None:
        create_task_execution_session(
            state,
            task_package=state.artifacts.current_task_package,
            step_name=step_name,
            role=AgentRole.PO,
            mode=resolve_kilo_mode(AgentRole.PO),
        )
        kilo_execution = execute_kilo_step(
            state,
            step_name=step_name,
            role=AgentRole.PO,
            task_package=state.artifacts.current_task_package,
            client=kilo_client or KiloExecutionClient(),
            metadata={"target_artifact": "TaskPackageCollection"},
        )
        state.metadata.setdefault("kilo", {})[step_name] = kilo_execution
        add_session_output(
            state,
            output_type="task_package_collection",
            content=(
                f"Prepared {len(task_packages)} TaskPackages and activated "
                f"{state.artifacts.current_task_package.task_id}."
            ),
            metadata={
                "task_package_count": len(task_packages),
                "current_task_id": state.artifacts.current_task_package.task_id,
            },
        )
    state.metadata.setdefault("artifact_sources", {})["task_packages"] = "prompt_pipeline"
    state.metadata.setdefault("prompt_pipeline", {})[step_name] = {
        "target_artifact": "TaskPackage",
        "count": len(task_packages),
        "task_ids": [task_package.task_id for task_package in task_packages],
        "provider_adapter": "fake",
    }
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.PO,
        metadata={
            "artifact": "TaskPackageCollection",
            "task_package_count": len(task_packages),
            "queue_id": state.metadata.get("queue_id"),
            "session_id": state.metadata.get("current_session_id"),
            "current_task_package": (
                state.artifacts.current_task_package.task_id
                if state.artifacts.current_task_package is not None
                else None
            ),
        },
    )


def po_final_validation_node(state: RuntimeState) -> RuntimeState:
    step_name = "po_final_validation"
    state = start_step(state, step_name=step_name, role=AgentRole.PO)
    state.artifacts.final_validation = {
        "issue_id": state.run.issue_id,
        "project": state.run.project,
        "approved": True,
        "summary": (
            "Functional validation completed on the simulated runtime output for "
            "the current TaskPackage."
        ),
    }
    state.run.status = WorkflowRunStatus.COMPLETED
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.PO,
        metadata={"artifact": "final_validation"},
    )
