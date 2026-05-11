from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from lummevia_reviews import (
    HumanReview,
    HumanReviewRegistry,
    ReviewDecision,
)


router = APIRouter(prefix="/reviews", tags=["reviews"])


class ReviewDecisionRequest(BaseModel):
    notes: str | None = None
    assigned_to: str | None = None


def _get_review_registry() -> HumanReviewRegistry:
    return HumanReviewRegistry.default()


@router.get("", response_model=list[HumanReview])
def list_reviews() -> list[HumanReview]:
    return _get_review_registry().list_reviews()


@router.get("/{review_id}", response_model=HumanReview)
def get_review(review_id: str) -> HumanReview:
    review = _get_review_registry().get_review(review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )
    return review


@router.post("/{review_id}/approve", response_model=HumanReview)
def approve_review(review_id: str, request: ReviewDecisionRequest) -> HumanReview:
    registry = _get_review_registry()
    review = registry.get_review(review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )
    return registry.complete_review(
        review_id,
        decision=ReviewDecision.APPROVED,
        notes=request.notes,
        assigned_to=request.assigned_to,
    )


@router.post("/{review_id}/reject", response_model=HumanReview)
def reject_review(review_id: str, request: ReviewDecisionRequest) -> HumanReview:
    registry = _get_review_registry()
    review = registry.get_review(review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review '{review_id}' not found.",
        )
    return registry.complete_review(
        review_id,
        decision=ReviewDecision.REJECTED,
        notes=request.notes,
        assigned_to=request.assigned_to,
    )
