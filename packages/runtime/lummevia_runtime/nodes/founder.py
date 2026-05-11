from __future__ import annotations

from lummevia_core import AgentRole
from lummevia_reviews import HumanReviewRegistry, ReviewDecision, ReviewType

from lummevia_runtime.events import complete_step, start_step
from lummevia_runtime.state import RuntimeState


def founder_input_node(state: RuntimeState) -> RuntimeState:
    step_name = "founder_input"
    state = start_step(state, step_name=step_name, role=AgentRole.FOUNDER)
    state.run.metadata["founder_input"] = {
        "summary": f"Initial founder intent captured for issue {state.run.issue_id}.",
        "project": state.run.project,
    }
    state.metadata["founder_intent_captured"] = True
    state.metadata["founder_approved"] = False
    state.metadata["business_brief_status"] = "draft"
    return complete_step(state, step_name=step_name, role=AgentRole.FOUNDER)


def founder_pm_conversation_node(state: RuntimeState) -> RuntimeState:
    step_name = "founder_pm_conversation"
    state = start_step(state, step_name=step_name, role=AgentRole.PM)
    state.run.metadata["founder_pm_conversation"] = {
        "status": "completed",
        "summary": (
            "Founder and PM iterated in a simulated chat loop before drafting "
            "the BusinessBrief."
        ),
        "iterations": 1,
    }
    return complete_step(
        state,
        step_name=step_name,
        role=AgentRole.PM,
        metadata={"conversation_loop": True, "iterations": 1},
    )


def founder_business_approval_node(state: RuntimeState) -> RuntimeState:
    step_name = "founder_business_approval"
    state = start_step(state, step_name=step_name, role=AgentRole.FOUNDER)
    business_brief = state.artifacts.business_brief
    if business_brief is None:
        raise ValueError("BusinessBrief must exist before founder approval.")
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

    state.artifacts.business_brief = business_brief.model_copy(
        update={
            "business_brief_status": "approved",
            "founder_approved": True,
        }
    )
    state.run.metadata["founder_business_approval"] = {
        "approved": True,
        "approved_by": AgentRole.FOUNDER.value,
        "review_id": review.review_id,
        "review_type": review.review_type.value,
        "review_status": review.status.value,
        "review_decision": review.decision.value if review.decision is not None else None,
    }
    state.metadata["founder_approved"] = True
    state.metadata["business_brief_status"] = "approved"
    state.metadata.setdefault("review_by_step", {})[step_name] = state.run.metadata[
        "founder_business_approval"
    ]
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
        },
    )
