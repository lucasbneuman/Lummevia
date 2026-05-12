from __future__ import annotations

from lummevia_reviews import HumanReview

from lummevia_persistence.repositories.base import SnapshotRepository


class ReviewSnapshotRepository(SnapshotRepository):
    entity_type = "review"

    def save_review(self, review: HumanReview):
        return self.save_snapshot(
            entity_type=self.entity_type,
            entity_id=review.review_id,
            payload=review.model_dump(mode="json"),
            metadata={"target_id": review.target_id, "status": review.status.value},
        )

    def list_reviews(self) -> list[HumanReview]:
        return [
            HumanReview.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.entity_type)
        ]
