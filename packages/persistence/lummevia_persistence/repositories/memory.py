from __future__ import annotations

from lummevia_memory import ProjectMemoryRecord

from lummevia_persistence.repositories.base import SnapshotRepository


class MemorySnapshotRepository(SnapshotRepository):
    entity_type = "memory_record"

    def save_record(self, record: ProjectMemoryRecord):
        return self.save_snapshot(
            entity_type=self.entity_type,
            entity_id=record.memory_id,
            payload=record.model_dump(mode="json"),
            metadata={"project": record.project, "source_id": record.source_id},
        )

    def list_records(self) -> list[ProjectMemoryRecord]:
        return [
            ProjectMemoryRecord.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.entity_type)
        ]
