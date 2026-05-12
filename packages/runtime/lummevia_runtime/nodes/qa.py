from __future__ import annotations

from lummevia_core import AgentRole, ValidationStatus
from lummevia_agents import QAAgent
from lummevia_kilo import KiloExecutionClient, resolve_kilo_mode
from lummevia_memory import (
    MemoryCategory,
    MemorySourceType,
    ProjectMemoryRegistry,
    build_project_memory_metadata,
)
from lummevia_reviews import HumanReviewRegistry, ReviewDecision, ReviewType
from lummevia_sessions import SessionStatus

from lummevia_runtime.events import complete_step, log_loop_reentered, start_step
from lummevia_runtime.kilo import execute_kilo_step
from lummevia_runtime.queue import mark_current_queue_item_completed, sync_task_queue_state
from lummevia_runtime.sessions import add_session_output, update_task_execution_session
from lummevia_runtime.state import RuntimeState


def qa_validation_node(
    state: RuntimeState,
    *,
    agent: QAAgent | None = None,
    kilo_client: KiloExecutionClient | None = None,
) -> RuntimeState:
    step_name = "qa_validation"
    task_package = state.artifacts.current_task_package
    if task_package is None:
        raise ValueError("TaskPackage must exist before QA validation.")

    state = start_step(state, step_name=step_name, role=AgentRole.QA)
    kilo_execution = execute_kilo_step(
        state,
        step_name=step_name,
        role=AgentRole.QA,
        task_package=task_package,
        client=kilo_client or KiloExecutionClient(),
        metadata={"target_artifact": "ValidationPackage"},
    )

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
    state.metadata.setdefault("kilo", {})[step_name] = kilo_execution
    state.metadata.setdefault("prompt_pipeline", {})[step_name] = pipeline_result.metadata
    add_session_output(
        state,
        output_type="validation_package",
        content=state.artifacts.validation_package.feedback,
        metadata={
            "task_id": task_package.task_id,
            "validation_status": state.artifacts.validation_package.status.value,
            "bugs_found": state.artifacts.validation_package.bugs_found,
        },
    )
    if state.artifacts.validation_package.status == ValidationStatus.FAILED:
        review = HumanReviewRegistry.default().create_review(
            review_type=ReviewType.QA_VALIDATION,
            target_id=task_package.task_id,
            target_type="TaskExecutionSession",
            requested_by=AgentRole.QA.value,
            assigned_to=AgentRole.FOUNDER.value,
            notes="QA failed. Session is waiting for review before the next iteration.",
            metadata={
                "issue_id": state.run.issue_id,
                "project": state.run.project,
                "task_id": task_package.task_id,
                "session_id": state.metadata.get("current_session_id"),
            },
        )
        memory_record = ProjectMemoryRegistry.default().add_memory(
            project=state.run.project,
            category=MemoryCategory.QA_ISSUE,
            title=f"QA issue for {task_package.task_id}",
            content=(
                f"QA failed for task {task_package.task_id}. "
                f"Feedback: {state.artifacts.validation_package.feedback}. "
                f"Bugs found: {', '.join(state.artifacts.validation_package.bugs_found) or 'none'}."
            ),
            source_type=MemorySourceType.REVIEW,
            source_id=review.review_id,
            tags=["qa", "issue", task_package.task_id, state.run.issue_id],
            metadata={
                "run_id": state.run.run_id,
                "issue_id": state.run.issue_id,
                "task_id": task_package.task_id,
                "session_id": state.metadata.get("current_session_id"),
            },
        )
        memory_metadata = build_project_memory_metadata(
            state.run.project,
            created_records=[memory_record],
        )
        qa_review_metadata = {
            "review_id": review.review_id,
            "review_type": review.review_type.value,
            "review_status": review.status.value,
            "review_decision": review.decision.value if review.decision is not None else None,
            "session_id": state.metadata.get("current_session_id"),
            "memory_id": memory_record.memory_id,
            **memory_metadata,
        }
        state.run.metadata[step_name] = qa_review_metadata
        state.metadata.setdefault("review_by_step", {})[step_name] = qa_review_metadata
        state.metadata.setdefault("memory_record_ids", []).append(memory_record.memory_id)
        state.metadata.update(memory_metadata)
        state.metadata["memory_records_created"] = len(state.metadata["memory_record_ids"])
        update_task_execution_session(
            state,
            status=SessionStatus.WAITING_REVIEW,
            role=AgentRole.QA,
            mode=resolve_kilo_mode(AgentRole.QA),
            metadata=qa_review_metadata,
        )
    else:
        mark_current_queue_item_completed(state)
        existing_review_id = (
            state.run.metadata.get(step_name, {}).get("review_id")
            or state.metadata.get("review_by_step", {}).get(step_name, {}).get("review_id")
        )
        if existing_review_id:
            review = HumanReviewRegistry.default().complete_review(
                existing_review_id,
                decision=ReviewDecision.APPROVED,
                notes="Auto-closed after simulated QA pass.",
                assigned_to=AgentRole.FOUNDER.value,
            )
            memory_record = ProjectMemoryRegistry.default().add_memory(
                project=state.run.project,
                category=MemoryCategory.REVIEW_DECISION,
                title=f"QA review decision for {task_package.task_id}",
                content=(
                    "QA validation review was completed after the rework loop. "
                    f"Decision: {review.decision.value if review.decision is not None else 'UNKNOWN'}."
                ),
                source_type=MemorySourceType.REVIEW,
                source_id=review.review_id,
                tags=["qa", "review", task_package.task_id, state.run.issue_id],
                metadata={
                    "run_id": state.run.run_id,
                    "issue_id": state.run.issue_id,
                    "task_id": task_package.task_id,
                    "session_id": state.metadata.get("current_session_id"),
                },
            )
            memory_metadata = build_project_memory_metadata(
                state.run.project,
                created_records=[memory_record],
            )
            qa_review_metadata = {
                "review_id": review.review_id,
                "review_type": review.review_type.value,
                "review_status": review.status.value,
                "review_decision": review.decision.value if review.decision is not None else None,
                "session_id": state.metadata.get("current_session_id"),
                "memory_id": memory_record.memory_id,
                **memory_metadata,
            }
            state.run.metadata[step_name] = qa_review_metadata
            state.metadata.setdefault("review_by_step", {})[step_name] = qa_review_metadata
            state.metadata.setdefault("memory_record_ids", []).append(memory_record.memory_id)
            state.metadata.update(memory_metadata)
            state.metadata["memory_records_created"] = len(state.metadata["memory_record_ids"])
        update_task_execution_session(
            state,
            status=SessionStatus.COMPLETED,
            role=AgentRole.QA,
            mode=resolve_kilo_mode(AgentRole.QA),
            metadata={
                "validation_status": state.artifacts.validation_package.status.value,
                "session_id": state.metadata.get("current_session_id"),
            },
        )
    if state.artifacts.validation_package.status == ValidationStatus.FAILED:
        sync_task_queue_state(state)
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
