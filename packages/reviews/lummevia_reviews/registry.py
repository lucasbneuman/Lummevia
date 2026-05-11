from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import uuid4

from lummevia_reviews.schemas import (
    HumanReview,
    ReviewDecision,
    ReviewStatus,
    ReviewType,
)


class HumanReviewRegistry:
    _default_instance: ClassVar["HumanReviewRegistry" | None] = None

    def __init__(self) -> None:
        self._reviews: dict[str, HumanReview] = {}

    @classmethod
    def default(cls) -> "HumanReviewRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._reviews.clear()

    def create_review(
        self,
        *,
        review_type: ReviewType,
        target_id: str,
        target_type: str,
        requested_by: str,
        notes: str = "",
        assigned_to: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> HumanReview:
        timestamp = datetime.now(UTC)
        review = HumanReview(
            review_id=f"review-{uuid4()}",
            review_type=review_type,
            target_id=target_id,
            target_type=target_type,
            requested_by=requested_by,
            assigned_to=assigned_to,
            status=ReviewStatus.PENDING,
            notes=notes,
            created_at=timestamp,
            updated_at=timestamp,
            metadata=metadata or {},
        )
        self._reviews[review.review_id] = review
        return review

    def get_review(self, review_id: str) -> HumanReview | None:
        return self._reviews.get(review_id)

    def list_reviews(self) -> list[HumanReview]:
        return list(self._reviews.values())

    def complete_review(
        self,
        review_id: str,
        *,
        decision: ReviewDecision,
        notes: str | None = None,
        assigned_to: str | None = None,
    ) -> HumanReview:
        review = self._reviews[review_id]
        updated = review.model_copy(
            update={
                "status": ReviewStatus.COMPLETED,
                "decision": decision,
                "notes": notes if notes is not None else review.notes,
                "assigned_to": assigned_to if assigned_to is not None else review.assigned_to,
                "updated_at": datetime.now(UTC),
            }
        )
        self._reviews[review_id] = updated
        return updated
