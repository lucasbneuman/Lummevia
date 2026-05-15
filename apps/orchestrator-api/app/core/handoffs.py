from __future__ import annotations

from typing import Any

from lummevia_conversations import ConversationPhase, ConversationRegistry, ConversationStatus
from lummevia_core import ApprovedProjectHandoff, ApprovedProjectHandoffRegistry, BusinessBrief


class ApprovedHandoffError(ValueError):
    """Raised when a conversation cannot be converted into an approved handoff."""


def create_or_get_approved_handoff(
    *,
    thread_id: str,
) -> ApprovedProjectHandoff:
    thread = ConversationRegistry.default().get_thread(thread_id)
    state = thread.founder_pm_state
    if thread.status != ConversationStatus.APPROVED or state is None:
        raise ApprovedHandoffError(
            f"Conversation thread '{thread_id}' is not approved for a project handoff."
        )
    if state.phase != ConversationPhase.APPROVED or not state.approved:
        raise ApprovedHandoffError(
            f"Conversation thread '{thread_id}' does not have an approved founder phase."
        )

    existing = ApprovedProjectHandoffRegistry.default().find_by_thread_version(
        thread_id=thread.thread_id,
        brief_version=state.brief_version,
    )
    if existing is not None:
        return existing

    approved_brief = dict(state.metadata.get("brief_draft", {}))
    if not approved_brief:
        raise ApprovedHandoffError(
            f"Conversation thread '{thread_id}' has no approved brief payload."
        )
    approved_brief["business_brief_status"] = "approved"
    approved_brief["founder_approved"] = True
    approved_brief.setdefault("issue_id", thread.issue_id)
    approved_brief.setdefault("project", thread.project)
    founder_summary = _extract_founder_summary(thread.messages)

    handoff = ApprovedProjectHandoffRegistry.default().save_handoff(
        ApprovedProjectHandoff(
            thread_id=thread.thread_id,
            issue_id=thread.issue_id,
            project=thread.project,
            approved_brief=approved_brief,
            brief_version=state.brief_version,
            founder_summary=founder_summary,
            metadata={
                "conversation_status": thread.status.value,
                "conversation_phase": state.phase.value,
                "message_count": len(thread.messages),
            },
        )
    )
    thread.metadata["handoff_id"] = handoff.handoff_id
    ConversationRegistry.default().save_thread(thread)
    return handoff


def create_or_get_run_for_handoff(
    *,
    handoff: ApprovedProjectHandoff,
):
    from app.api.routes import runtime as runtime_routes
    from lummevia_runtime import PersistedRunNotFoundError, RuntimeNotFoundError

    workflow_run_id = str(handoff.metadata.get("workflow_run_id", "")).strip()
    if workflow_run_id:
        try:
            return runtime_routes.runtime_service.get_run(workflow_run_id)
        except RuntimeNotFoundError:
            if runtime_routes.runtime_repository is not None:
                try:
                    return runtime_routes.runtime_repository.get_run(workflow_run_id)
                except PersistedRunNotFoundError:
                    pass

    approved_brief = BusinessBrief.model_validate(
        {
            key: value
            for key, value in handoff.approved_brief.items()
            if key
            in {
                "issue_id",
                "project",
                "objective",
                "problem",
                "expected_impact",
                "priority",
                "constraints",
                "non_goals",
                "kpis",
                "business_brief_status",
                "founder_approved",
            }
        }
    )
    state = runtime_routes.runtime_service.start_run(
        project=handoff.project,
        issue_id=handoff.issue_id,
        initial_metadata={
            "approved_brief": approved_brief.model_dump(mode="json"),
            "conversation_thread_id": handoff.thread_id,
            "thread_id": handoff.thread_id,
            "handoff_id": handoff.handoff_id,
            "brief_version": handoff.brief_version,
            "founder_input": {
                "summary": handoff.founder_summary,
                "project": handoff.project,
            },
        },
    )
    handoff.metadata["workflow_run_id"] = state.run.run_id
    handoff.metadata["workflow_status"] = state.run.status.value
    ApprovedProjectHandoffRegistry.default().save_handoff(handoff)
    return state


def create_or_get_handoff_and_run(
    *,
    thread_id: str,
) -> tuple[ApprovedProjectHandoff, Any]:
    handoff = create_or_get_approved_handoff(thread_id=thread_id)
    state = create_or_get_run_for_handoff(handoff=handoff)
    return handoff, state


def _extract_founder_summary(messages: list[Any]) -> str:
    for message in messages:
        if getattr(message, "author_type", None) is not None and message.author_type.value == "FOUNDER":
            content = str(getattr(message, "content", "")).strip()
            if content:
                return content
    return "Founder approval captured from the conversation thread."
