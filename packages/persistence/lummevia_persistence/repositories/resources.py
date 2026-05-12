from __future__ import annotations

from lummevia_resources import ResourceLock, WorkspaceAllocation

from lummevia_persistence.repositories.base import SnapshotRepository


class ResourceSnapshotRepository(SnapshotRepository):
    lock_entity_type = "resource_lock"
    workspace_entity_type = "workspace"

    def save_lock(self, lock: ResourceLock):
        return self.save_snapshot(
            entity_type=self.lock_entity_type,
            entity_id=lock.lock_id,
            payload=lock.model_dump(mode="json"),
            metadata={"resource_type": lock.resource_type.value, "resource_id": lock.resource_id},
        )

    def save_workspace(self, workspace: WorkspaceAllocation):
        return self.save_snapshot(
            entity_type=self.workspace_entity_type,
            entity_id=workspace.workspace_id,
            payload=workspace.model_dump(mode="json"),
            metadata={"project": workspace.project, "repo": workspace.repo, "status": workspace.status.value},
        )

    def list_locks(self) -> list[ResourceLock]:
        return [
            ResourceLock.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.lock_entity_type)
        ]

    def list_workspaces(self) -> list[WorkspaceAllocation]:
        return [
            WorkspaceAllocation.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.workspace_entity_type)
        ]
