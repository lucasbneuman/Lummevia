from __future__ import annotations

from collections.abc import Callable

from lummevia_conversations import (
    AuthorType,
    ConversationPhase,
    ConversationRegistry,
    ConversationStatus,
    ConversationThreadNotFoundError,
    apply_founder_message_policy,
    build_approval_state,
    build_initial_founder_pm_state,
    update_thread_with_policy_decision,
)
from lummevia_core import AgentRole
from lummevia_memory import (
    MemoryCategory,
    MemorySourceType,
    ProjectMemoryRegistry,
    build_project_memory_metadata,
)
from lummevia_reviews import HumanReviewRegistry, ReviewDecision, ReviewType

from lummevia_runtime.events import complete_step, start_step
from lummevia_runtime.state import RuntimeState


def founder_input_node(state: RuntimeState) -> RuntimeState:
    step_name = "founder_input"
    state = start_step(state, step_name=step_name, role=AgentRole.FOUNDER)
    state.run.metadata.setdefault(
        "founder_input",
        {
            "summary": f"Initial founder intent captured for issue {state.run.issue_id}.",
            "project": state.run.project,
        },
    )
    state.metadata["founder_intent_captured"] = True
    state.metadata["founder_approved"] = False
    state.metadata["business_brief_status"] = "draft"
    state.metadata["conversation_phase"] = ConversationPhase.STARTED.value
    state.metadata["brief_version"] = 0
    state.metadata["pending_questions_count"] = 0
    return complete_step(state, step_name=step_name, role=AgentRole.FOUNDER)


def founder_pm_conversation_node(
    state: RuntimeState,
    *,
    agent=None,
    artifact_publisher: Callable[[str, str, dict], None] | None = None,
) -> RuntimeState:
    step_name = "founder_pm_conversation"
    state = start_step(state, step_name=step_name, role=AgentRole.PM)
    registry = ConversationRegistry.default()
    founder_input = state.run.metadata.get("founder_input", {})
    founder_message = founder_input.get(
        "summary",
        f"Initial founder intent captured for issue {state.run.issue_id}.",
    )
    thread_id = (
        str(state.run.metadata.get("conversation_thread_id", "")).strip()
        or str(state.metadata.get("thread_id", "")).strip()
    )
    if thread_id:
        try:
            thread = registry.get_thread(thread_id)
        except ConversationThreadNotFoundError:
            thread = _create_runtime_thread(
                registry,
                state=state,
                seed_thread_id=thread_id,
            )
    else:
        thread = _create_runtime_thread(registry, state=state)

    thread = registry.add_message(
        thread.thread_id,
        role="user",
        author_type=AuthorType.FOUNDER,
        content=founder_message,
        metadata={
            "iteration": 0,
            "kind": "initial_intent",
            "conversation_event": "FOUNDER_RESPONSE_RECEIVED",
        },
    )

    decision = apply_founder_message_policy(thread, founder_message=founder_message)
    thread = update_thread_with_policy_decision(thread, decision)
    registry.save_thread(thread)

    if decision.last_pm_message is not None:
        thread = registry.add_message(
            thread.thread_id,
            role="assistant",
            author_type=AuthorType.PM,
            content=decision.last_pm_message,
            metadata={
                "iteration": decision.iteration_count,
                "conversation_event": "PM_QUESTION_SENT",
                "pending_questions_count": len(decision.pending_questions),
            },
        )

    if decision.phase == ConversationPhase.PM_QUESTIONS:
        founder_feedback = (
            "Usuario principal: recepcionistas y pacientes.\n"
            "Alcance MVP: crear reserva, confirmar turno y ver agenda diaria.\n"
            "Restricciones: sin autoaprobacion, sin chatbot libre y sin multiples PM.\n"
            "Exito esperado: validar que se pueda crear y confirmar una reserva end to end."
        )
        thread = registry.add_message(
            thread.thread_id,
            role="user",
            author_type=AuthorType.FOUNDER,
            content=founder_feedback,
            metadata={
                "iteration": decision.iteration_count,
                "kind": "simulated_founder_reply",
                "conversation_event": "FOUNDER_RESPONSE_RECEIVED",
            },
        )
        decision = apply_founder_message_policy(thread, founder_message=founder_feedback)
        thread = update_thread_with_policy_decision(thread, decision)
        registry.save_thread(thread)
        if decision.last_pm_message is not None:
            thread = registry.add_message(
                thread.thread_id,
                role="assistant",
                author_type=AuthorType.PM,
                content=decision.last_pm_message,
                metadata={
                    "iteration": decision.iteration_count,
                    "conversation_event": "BRIEF_DRAFT_CREATED",
                    "brief_version": decision.brief_version,
                },
            )

    memory_record = ProjectMemoryRegistry.default().add_memory(
        project=state.run.project,
        category=MemoryCategory.BUSINESS_DECISION,
        title=f"Founder decision for {state.run.issue_id}",
        content=(
            f"Founder intent: {founder_message}\n\n"
            f"Conversation phase: {decision.phase.value}\n"
            f"Pending questions: {len(decision.pending_questions)}\n"
            f"Brief version: {decision.brief_version}"
        ),
        source_type=MemorySourceType.CONVERSATION,
        source_id=thread.thread_id,
        tags=["founder", "pm", "business-brief", state.run.issue_id],
        metadata={
            "run_id": state.run.run_id,
            "issue_id": state.run.issue_id,
            "conversation_status": thread.status.value,
            "conversation_phase": decision.phase.value,
        },
    )
    memory_metadata = build_project_memory_metadata(
        state.run.project,
        created_records=[memory_record],
    )

    state.run.metadata["founder_pm_conversation"] = {
        "status": "completed",
        "summary": "Founder and PM iterated under the contractual conversation policy.",
        "thread_id": thread.thread_id,
        "conversation_status": thread.status.value,
        "conversation_phase": decision.phase.value,
        "iteration_count": decision.iteration_count,
        "pending_questions_count": len(decision.pending_questions),
        "brief_version": decision.brief_version,
        "message_count": len(thread.messages),
        "brief_draft": decision.brief_draft,
        "memory_id": memory_record.memory_id,
        **memory_metadata,
    }
    state.run.metadata.setdefault("persistence", {})["thread_id"] = thread.thread_id
    state.run.metadata["conversation_thread_id"] = thread.thread_id
    state.metadata["thread_id"] = thread.thread_id
    state.metadata["conversation_status"] = thread.status.value
    state.metadata["conversation_phase"] = decision.phase.value
    state.metadata["iteration_count"] = decision.iteration_count
    state.metadata["brief_version"] = decision.brief_version
    state.metadata["pending_questions_count"] = len(decision.pending_questions)
    state.metadata["message_count"] = len(thread.messages)
    state.metadata["conversation_thread"] = thread.model_dump(mode="json")
    state.metadata.setdefault("memory_record_ids", []).append(memory_record.memory_id)
    state.metadata.update(memory_metadata)
    state.metadata["memory_records_created"] = len(state.metadata["memory_record_ids"])
    if artifact_publisher is not None:
        artifact_publisher(
            state.run.issue_id,
            "FounderPmConversation",
            {
                "thread_id": thread.thread_id,
                "message_count": len(thread.messages),
                "conversation_status": thread.status.value,
                "conversation_phase": decision.phase.value,
                "brief_version": decision.brief_version,
            },
        )
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.PM,
        metadata={
            "conversation_loop": True,
            "iterations": decision.iteration_count,
            "thread_id": thread.thread_id,
            "message_count": len(thread.messages),
            "conversation_phase": decision.phase.value,
            "brief_version": decision.brief_version,
            "pending_questions_count": len(decision.pending_questions),
            "memory_id": memory_record.memory_id,
        },
    )


def founder_business_approval_node(
    state: RuntimeState,
    *,
    artifact_publisher: Callable[[str, str, dict], None] | None = None,
) -> RuntimeState:
    step_name = "founder_business_approval"
    state = start_step(state, step_name=step_name, role=AgentRole.FOUNDER)
    business_brief = state.artifacts.business_brief
    if business_brief is None:
        raise ValueError("BusinessBrief must exist before founder approval.")
    thread_id = str(state.metadata.get("thread_id", "")).strip()
    if not thread_id:
        raise ValueError("Conversation thread must exist before founder approval.")
    conversation_registry = ConversationRegistry.default()
    thread = conversation_registry.get_thread(thread_id)
    review_registry = HumanReviewRegistry.default()
    review = review_registry.create_review(
        review_type=ReviewType.BUSINESS_BRIEF,
        target_id=business_brief.issue_id,
        target_type="BusinessBrief",
        requested_by=AgentRole.PM.value,
        assigned_to=AgentRole.FOUNDER.value,
        notes="Founder approval gate for BusinessBrief.",
        metadata={
            "issue_id": business_brief.issue_id,
            "project": business_brief.project,
            "business_brief_status": business_brief.business_brief_status,
            "run_id": state.run.run_id,
            "thread_id": thread.thread_id,
        },
    )
    review = review_registry.complete_review(
        review.review_id,
        decision=ReviewDecision.APPROVED,
        notes="Auto-approved by the simulated founder flow.",
        assigned_to=AgentRole.FOUNDER.value,
    )

    thread_state = thread.founder_pm_state
    if thread_state is None:
        raise ValueError("Conversation state must exist before founder approval.")
    approved_state = build_approval_state(
        thread_state,
        approval_message="approve",
        review_id=review.review_id,
    )
    thread = thread.model_copy(
        update={
            "status": ConversationStatus.APPROVED,
            "founder_pm_state": approved_state,
        }
    )
    conversation_registry.save_thread(thread)

    memory_record = ProjectMemoryRegistry.default().add_memory(
        project=state.run.project,
        category=MemoryCategory.REVIEW_DECISION,
        title=f"Founder review decision for {business_brief.issue_id}",
        content=(
            "Founder approved the BusinessBrief after the PM conversation gate. "
            f"Decision: {review.decision.value if review.decision is not None else 'UNKNOWN'}."
        ),
        source_type=MemorySourceType.REVIEW,
        source_id=review.review_id,
        tags=["founder", "review", "business-brief", business_brief.issue_id],
        metadata={
            "run_id": state.run.run_id,
            "issue_id": business_brief.issue_id,
            "review_type": review.review_type.value,
            "review_status": review.status.value,
        },
    )
    memory_metadata = build_project_memory_metadata(
        state.run.project,
        created_records=[memory_record],
    )

    state.artifacts.business_brief = business_brief.model_copy(
        update={
            "business_brief_status": "approved",
            "founder_approved": True,
        }
    )
    state.run.metadata["founder_business_approval"] = {
        "approved": True,
        "approved_by": AgentRole.FOUNDER.value,
        "thread_id": thread.thread_id,
        "conversation_status": thread.status.value,
        "conversation_phase": approved_state.phase.value,
        "brief_version": approved_state.brief_version,
        "message_count": len(thread.messages),
        "review_id": review.review_id,
        "review_type": review.review_type.value,
        "review_status": review.status.value,
        "review_decision": review.decision.value if review.decision is not None else None,
        "memory_id": memory_record.memory_id,
        **memory_metadata,
    }
    state.run.metadata.setdefault("persistence", {})["thread_id"] = thread.thread_id
    state.metadata["founder_approved"] = True
    state.metadata["business_brief_status"] = "approved"
    state.metadata["business_brief_thread_id"] = thread.thread_id
    state.metadata["thread_id"] = thread.thread_id
    state.metadata["conversation_status"] = thread.status.value
    state.metadata["conversation_phase"] = approved_state.phase.value
    state.metadata["brief_version"] = approved_state.brief_version
    state.metadata["pending_questions_count"] = 0
    state.metadata["message_count"] = len(thread.messages)
    state.metadata["conversation_thread"] = thread.model_dump(mode="json")
    state.metadata.setdefault("review_by_step", {})[step_name] = state.run.metadata[
        "founder_business_approval"
    ]
    state.metadata.setdefault("memory_record_ids", []).append(memory_record.memory_id)
    state.metadata.update(memory_metadata)
    state.metadata["memory_records_created"] = len(state.metadata["memory_record_ids"])
    if artifact_publisher is not None:
        artifact_publisher(
            business_brief.issue_id,
            "BusinessBriefApproved",
            {
                "thread_id": thread.thread_id,
                "review_id": review.review_id,
                "review_decision": review.decision.value if review.decision is not None else None,
                "conversation_status": thread.status.value,
                "conversation_phase": approved_state.phase.value,
                "brief_version": approved_state.brief_version,
            },
        )
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.FOUNDER,
        metadata={
            "artifact": "BusinessBriefApproved",
            "founder_approved": True,
            "business_brief_status": "approved",
            "conversation_phase": approved_state.phase.value,
            "brief_version": approved_state.brief_version,
            "review_id": review.review_id,
            "review_type": review.review_type.value,
            "review_status": review.status.value,
            "review_decision": review.decision.value if review.decision is not None else None,
            "memory_id": memory_record.memory_id,
        },
    )


def _create_runtime_thread(
    registry: ConversationRegistry,
    *,
    state: RuntimeState,
    seed_thread_id: str | None = None,
):
    founder_pm_state = build_initial_founder_pm_state(
        thread_id=seed_thread_id or "seed-thread-id",
        project=state.run.project,
        issue_id=state.run.issue_id,
        telegram_chat_id=None,
        metadata={
            "run_id": state.run.run_id,
            "workflow": state.run.workflow_name,
        },
    )
    thread = registry.create_thread(
        topic=f"Founder strategic iteration for {state.run.issue_id}",
        project=state.run.project,
        issue_id=state.run.issue_id,
        founder_pm_state=founder_pm_state,
        metadata={
            "run_id": state.run.run_id,
            "workflow": state.run.workflow_name,
            **({"seed_thread_id": seed_thread_id} if seed_thread_id else {}),
        },
    )
    thread = thread.model_copy(
        update={
            "founder_pm_state": founder_pm_state.model_copy(
                update={"thread_id": thread.thread_id}
            )
        }
    )
    registry.save_thread(thread)
    return thread
