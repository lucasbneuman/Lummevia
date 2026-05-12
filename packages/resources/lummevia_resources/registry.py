from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from lummevia_resources.schemas import (
    ResourceLock,
    ResourceLockStatus,
    ResourceType,
    WorkspaceAllocation,
    WorkspaceStatus,
)


class ResourceRegistry:
    _default_instance: ClassVar["ResourceRegistry" | None] = None

    def __init__(self) -> None:
        self._locks: dict[str, ResourceLock] = {}
        self._workspaces: dict[str, WorkspaceAllocation] = {}
        self._persistence = None

    @classmethod
    def default(cls) -> "ResourceRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._locks.clear()
        self._workspaces.clear()

    def configure_persistence(self, persistence) -> None:
        self._persistence = persistence

    def rehydrate(
        self,
        *,
        locks: list[ResourceLock],
        workspaces: list[WorkspaceAllocation],
    ) -> None:
        self._locks = {lock.lock_id: lock for lock in locks}
        self._workspaces = {workspace.workspace_id: workspace for workspace in workspaces}

    def acquire_lock(
        self,
        *,
        resource_type: ResourceType,
        resource_id: str,
        owner_id: str,
        owner_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> ResourceLock:
        active_lock = self.find_active_lock(
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if active_lock is not None:
            if (
                active_lock.owner_id == owner_id
                and active_lock.owner_type == owner_type
            ):
                return active_lock
            raise ValueError(
                "Resource already has an active lock for "
                f"{resource_type.value}:{resource_id}."
            )
        lock = ResourceLock(
            resource_type=resource_type,
            resource_id=resource_id,
            owner_id=owner_id,
            owner_type=owner_type,
            metadata=metadata or {},
        )
        self._locks[lock.lock_id] = lock
        self._persist_lock(lock)
        return lock

    def release_lock(
        self,
        lock_id: str,
        *,
        metadata: dict[str, Any] | None = None,
        status: ResourceLockStatus = ResourceLockStatus.RELEASED,
    ) -> ResourceLock:
        lock = self._locks[lock_id]
        merged_metadata = {**lock.metadata, **(metadata or {})}
        released = lock.model_copy(
            update={
                "status": status,
                "released_at": datetime.now(UTC),
                "metadata": merged_metadata,
            }
        )
        self._locks[lock_id] = released
        self._persist_lock(released)
        return released

    def get_lock(self, lock_id: str) -> ResourceLock | None:
        return self._locks.get(lock_id)

    def list_locks(self) -> list[ResourceLock]:
        return sorted(
            self._locks.values(),
            key=lambda lock: (lock.acquired_at, lock.lock_id),
            reverse=True,
        )

    def list_active_locks(self) -> list[ResourceLock]:
        return [
            lock
            for lock in self.list_locks()
            if lock.status == ResourceLockStatus.ACQUIRED
        ]

    def find_active_lock(
        self,
        *,
        resource_type: ResourceType,
        resource_id: str,
    ) -> ResourceLock | None:
        return next(
            (
                lock
                for lock in self.list_active_locks()
                if lock.resource_type == resource_type
                and lock.resource_id == resource_id
            ),
            None,
        )

    def save_workspace(self, workspace: WorkspaceAllocation) -> WorkspaceAllocation:
        self._workspaces[workspace.workspace_id] = workspace
        self._persist_workspace(workspace)
        return workspace

    def get_workspace(self, workspace_id: str) -> WorkspaceAllocation | None:
        return self._workspaces.get(workspace_id)

    def list_workspaces(self) -> list[WorkspaceAllocation]:
        return sorted(
            self._workspaces.values(),
            key=lambda workspace: (workspace.created_at, workspace.workspace_id),
            reverse=True,
        )

    def update_workspace(
        self,
        workspace_id: str,
        *,
        status: WorkspaceStatus | None = None,
        metadata: dict[str, Any] | None = None,
        released_at: datetime | None = None,
    ) -> WorkspaceAllocation:
        workspace = self._workspaces[workspace_id]
        merged_metadata = {**workspace.metadata, **(metadata or {})}
        updated = workspace.model_copy(
            update={
                "status": status or workspace.status,
                "released_at": released_at,
                "metadata": merged_metadata,
            }
        )
        self._workspaces[workspace_id] = updated
        self._persist_workspace(updated)
        return updated

    def _persist_lock(self, lock: ResourceLock) -> None:
        if self._persistence is None:
            return
        try:
            self._persistence.save_lock(lock)
        except Exception:
            return

    def _persist_workspace(self, workspace: WorkspaceAllocation) -> None:
        if self._persistence is None:
            return
        try:
            self._persistence.save_workspace(workspace)
        except Exception:
            return
