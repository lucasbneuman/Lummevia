from __future__ import annotations

from lummevia_reviews import (
    HumanReviewRegistry,
    ReviewDecision,
    ReviewStatus,
    ReviewType,
)


def test_review_registry_creates_and_lists_reviews() -> None:
    registry = HumanReviewRegistry()

    created = registry.create_review(
        review_type=ReviewType.TASK_PLAN,
        target_id="plan-001",
        target_type="TaskPlan",
        requested_by="po",
        notes="Need human check before execution.",
        metadata={"issue_id": "OS-200"},
    )

    assert created.review_id
    assert created.status is ReviewStatus.PENDING
    assert created.decision is None
    assert created.metadata["issue_id"] == "OS-200"
    assert registry.get_review(created.review_id) == created
    assert registry.list_reviews() == [created]


def test_review_registry_completes_reviews_with_decisions() -> None:
    registry = HumanReviewRegistry()
    created = registry.create_review(
        review_type=ReviewType.QC_APPROVAL,
        target_id="pr-12",
        target_type="PullRequest",
        requested_by="qc",
        notes="Final approval required.",
    )

    approved = registry.complete_review(
        created.review_id,
        decision=ReviewDecision.APPROVED,
        notes="Approved by human reviewer.",
        assigned_to="founder",
    )

    assert approved.status is ReviewStatus.COMPLETED
    assert approved.decision is ReviewDecision.APPROVED
    assert approved.assigned_to == "founder"
    assert approved.notes == "Approved by human reviewer."

    rejected = registry.create_review(
        review_type=ReviewType.QA_VALIDATION,
        target_id="validation-1",
        target_type="ValidationPackage",
        requested_by="qa",
        notes="Edge case still open.",
    )
    rejected = registry.complete_review(
        rejected.review_id,
        decision=ReviewDecision.REJECTED,
        notes="Rejected pending fixes.",
    )

    assert rejected.status is ReviewStatus.COMPLETED
    assert rejected.decision is ReviewDecision.REJECTED
