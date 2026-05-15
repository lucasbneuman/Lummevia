from __future__ import annotations

from lummevia_core import ApprovedProjectHandoff

from lummevia_persistence.repositories.base import SnapshotRepository


class ApprovedProjectHandoffSnapshotRepository(SnapshotRepository):
    entity_type = "handoff"

    def save_handoff(self, handoff: ApprovedProjectHandoff):
        return self.save_snapshot(
            entity_type=self.entity_type,
            entity_id=handoff.handoff_id,
            payload=handoff.model_dump(mode="json"),
            metadata={
                "project": handoff.project,
                "issue_id": handoff.issue_id,
                "thread_id": handoff.thread_id,
                "brief_version": handoff.brief_version,
            },
        )

    def list_handoffs(self) -> list[ApprovedProjectHandoff]:
        return [
            ApprovedProjectHandoff.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.entity_type)
        ]
