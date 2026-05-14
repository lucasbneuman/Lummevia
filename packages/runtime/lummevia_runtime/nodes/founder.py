from __future__ import annotations

from collections.abc import Callable

from lummevia_agents import PMAgent
from lummevia_conversations import (
    AuthorType,
    ConversationRegistry,
    ConversationStatus,
    ConversationThreadNotFoundError,
)
from lummevia_core import AgentRole
from lummevia_memory import (
    MemoryCategory,
    MemorySourceType,
    ProjectMemoryRegistry,
    build_project_memory_metadata,
)
from lummevia_reviews import HumanReviewRegistry, ReviewDecision, ReviewType

from lummevia_runtime.economics import register_model_execution_cost
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
    return complete_step(state, step_name=step_name, role=AgentRole.FOUNDER)


def founder_pm_conversation_node(
    state: RuntimeState,
    *,
    agent: PMAgent | None = None,
    artifact_publisher: Callable[[str, str, dict], None] | None = None,
) -> RuntimeState:
    step_name = "founder_pm_conversation"
    state = start_step(state, step_name=step_name, role=AgentRole.PM)
    registry = ConversationRegistry.default()
    pm_agent = agent or PMAgent()
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
            thread = registry.create_thread(
                topic=f"Founder strategic iteration for {state.run.issue_id}",
                project=state.run.project,
                issue_id=state.run.issue_id,
                metadata={
                    "run_id": state.run.run_id,
                    "workflow": state.run.workflow_name,
                    "seed_thread_id": thread_id,
                },
            )
    else:
        thread = registry.create_thread(
            topic=f"Founder strategic iteration for {state.run.issue_id}",
            project=state.run.project,
            issue_id=state.run.issue_id,
            metadata={
                "run_id": state.run.run_id,
                "workflow": state.run.workflow_name,
            },
        )
    thread = registry.add_message(
        thread.thread_id,
        role="user",
        author_type=AuthorType.FOUNDER,
        content=founder_message,
        metadata={"iteration": 1, "kind": "initial_intent"},
    )
    pm_response = pm_agent.execute_model(
        (
            "Founder intent:\n"
            f"{founder_message}\n\n"
            "Respond as PM with a short strategic alignment summary, "
            "proposed scope, and one concise next-step recommendation."
        ),
        project=state.run.project,
        metadata={
            "run_id": state.run.run_id,
            "step_name": step_name,
            "conversation_thread_id": thread.thread_id,
            "conversation_mode": "founder_pm_iteration",
        },
    )
    register_model_execution_cost(
        state,
        step_name=step_name,
        execution=pm_response,
    )
    thread = registry.add_message(
        thread.thread_id,
        role="assistant",
        author_type=AuthorType.PM,
        content=pm_response.output,
        metadata={
            "iteration": 1,
            "provider": pm_response.provider,
            "model": pm_response.model,
            "effective_provider": pm_response.effective_provider,
            "effective_model": pm_response.effective_model,
            "fallback_used": pm_response.fallback_used,
        },
    )
    founder_feedback = (
        "Founder feedback: proceed with a narrowed first iteration and keep the "
        "brief in draft until explicit approval."
    )
    thread = registry.add_message(
        thread.thread_id,
        role="user",
        author_type=AuthorType.FOUNDER,
        content=founder_feedback,
        metadata={"iteration": 1, "kind": "feedback"},
    )
    memory_record = ProjectMemoryRegistry.default().add_memory(
        project=state.run.project,
        category=MemoryCategory.BUSINESS_DECISION,
        title=f"Founder decision for {state.run.issue_id}",
        content=(
            f"Founder intent: {founder_message}\n\n"
            f"PM alignment: {pm_response.output}\n\n"
            f"Founder feedback: {founder_feedback}"
        ),
        source_type=MemorySourceType.CONVERSATION,
        source_id=thread.thread_id,
        tags=["founder", "pm", "business-brief", state.run.issue_id],
        metadata={
            "run_id": state.run.run_id,
            "issue_id": state.run.issue_id,
            "conversation_status": thread.status.value,
        },
    )
    memory_metadata = build_project_memory_metadata(
        state.run.project,
        created_records=[memory_record],
    )

    state.run.metadata["founder_pm_conversation"] = {
        "status": "completed",
        "summary": (
            "Founder and PM completed one strategic iteration before drafting "
            "the BusinessBrief."
        ),
        "thread_id": thread.thread_id,
        "conversation_status": thread.status.value,
        "iteration_count": 1,
        "message_count": len(thread.messages),
        "provider": pm_response.provider,
        "model": pm_response.model,
        "effective_provider": pm_response.effective_provider,
        "effective_model": pm_response.effective_model,
        "fallback_used": pm_response.fallback_used,
        "memory_id": memory_record.memory_id,
        **memory_metadata,
    }
    state.run.metadata.setdefault("persistence", {})["thread_id"] = thread.thread_id
    state.run.metadata["conversation_thread_id"] = thread.thread_id
    state.metadata["thread_id"] = thread.thread_id
    state.metadata["conversation_status"] = thread.status.value
    state.metadata["iteration_count"] = 1
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
            },
        )
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.PM,
        metadata={
            "conversation_loop": True,
            "iterations": 1,
            "thread_id": thread.thread_id,
            "message_count": len(thread.messages),
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
    thread = conversation_registry.update_thread_status(
        thread_id,
        ConversationStatus.APPROVED,
        metadata={
            "business_brief_issue_id": business_brief.issue_id,
            "business_brief_status": "approved",
        },
    )
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
        },
    )
    review = review_registry.complete_review(
        review.review_id,
        decision=ReviewDecision.APPROVED,
        notes="Auto-approved by the simulated founder flow.",
        assigned_to=AgentRole.FOUNDER.value,
    )
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
            "review_id": review.review_id,
            "review_type": review.review_type.value,
            "review_status": review.status.value,
            "review_decision": review.decision.value if review.decision is not None else None,
            "memory_id": memory_record.memory_id,
        },
    )
