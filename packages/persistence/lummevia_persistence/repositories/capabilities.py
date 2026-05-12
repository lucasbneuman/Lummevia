from __future__ import annotations

from typing import Any

from lummevia_persistence.repositories.base import SnapshotRepository


class CapabilitySnapshotRepository(SnapshotRepository):
    entity_type = "capability_state"

    def save_snapshot_state(self, entity_id: str, payload: dict[str, Any]):
        return self.save_snapshot(
            entity_type=self.entity_type,
            entity_id=entity_id,
            payload=payload,
            metadata={"kind": entity_id},
        )

    def list_states(self) -> list[dict[str, Any]]:
        return [snapshot.payload for snapshot in self.list_latest_snapshots(self.entity_type)]
