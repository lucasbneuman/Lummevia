from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath
from uuid import NAMESPACE_URL, uuid5

from lummevia_core import TaskPackage
from lummevia_queue import TaskQueueItem

from lummevia_resources.registry import ResourceRegistry
from lummevia_resources.schemas import (
    ResourceType,
    WorkspaceAllocation,
    WorkspaceStatus,
)


DEFAULT_WORKSPACE_ROOT = "/virtual/kilo-workspaces"


class WorkspaceAllocator:
    def __init__(
        self,
        registry: ResourceRegistry | None = None,
        *,
        workspace_root: str | None = None,
    ) -> None:
        self.registry = registry or ResourceRegistry.default()
        configured_root = workspace_root or os.getenv("KILO_WORKSPACE_ROOT")
        self.workspace_root = configured_root or DEFAULT_WORKSPACE_ROOT

    def allocate_workspace(
        self,
        task_package: TaskPackage,
        queue_item: TaskQueueItem,
    ) -> WorkspaceAllocation:
        repo = task_package.target_repo
        workspace_id = self._build_workspace_id(
            project=task_package.project,
            repo=repo,
            task_id=task_package.task_id,
            queue_item_id=queue_item.queue_item_id,
        )
        existing = self.registry.get_workspace(workspace_id)
        if existing is not None and existing.status != WorkspaceStatus.RELEASED:
            return existing

        branch_name = self._build_branch_name(
            project=task_package.project,
            task_id=task_package.task_id,
            queue_item_id=queue_item.queue_item_id,
        )
        worktree_path = self._build_worktree_path(
            project=task_package.project,
            workspace_id=workspace_id,
        )
        owner_id = queue_item.queue_item_id
        lock_metadata = {
            "project": task_package.project,
            "repo": repo,
            "task_id": task_package.task_id,
            "workspace_id": workspace_id,
            "branch_name": branch_name,
            "worktree_path": worktree_path,
            "simulated": True,
        }
        repo_lock = self.registry.acquire_lock(
            resource_type=ResourceType.REPO,
            resource_id=repo,
            owner_id=owner_id,
            owner_type="TaskQueueItem",
            metadata=lock_metadata,
        )
        workspace_lock = self.registry.acquire_lock(
            resource_type=ResourceType.WORKSPACE,
            resource_id=workspace_id,
            owner_id=owner_id,
            owner_type="TaskQueueItem",
            metadata=lock_metadata,
        )
        path_lock = self.registry.acquire_lock(
            resource_type=ResourceType.PATH,
            resource_id=worktree_path,
            owner_id=owner_id,
            owner_type="TaskQueueItem",
            metadata=lock_metadata,
        )
        return self.registry.save_workspace(
            WorkspaceAllocation(
                workspace_id=workspace_id,
                project=task_package.project,
                repo=repo,
                task_id=task_package.task_id,
                queue_item_id=queue_item.queue_item_id,
                branch_name=branch_name,
                worktree_path=worktree_path,
                status=WorkspaceStatus.ALLOCATED,
                metadata={
                    **lock_metadata,
                    "lock_ids": [
                        repo_lock.lock_id,
                        workspace_lock.lock_id,
                        path_lock.lock_id,
                    ],
                },
            )
        )

    def mark_workspace_active(
        self,
        workspace_id: str,
        *,
        metadata: dict[str, object] | None = None,
    ) -> WorkspaceAllocation:
        return self.registry.update_workspace(
            workspace_id,
            status=WorkspaceStatus.ACTIVE,
            metadata=metadata or {},
        )

    def release_workspace(
        self,
        workspace_id: str,
        *,
        metadata: dict[str, object] | None = None,
        status: WorkspaceStatus = WorkspaceStatus.RELEASED,
    ) -> WorkspaceAllocation:
        workspace = self.registry.get_workspace(workspace_id)
        if workspace is None:
            raise KeyError(f"Workspace '{workspace_id}' not found.")
        merged_metadata = {**workspace.metadata, **(metadata or {})}
        for lock_id in workspace.metadata.get("lock_ids", []):
            self.registry.release_lock(
                str(lock_id),
                metadata={
                    "workspace_id": workspace_id,
                    "workspace_status": status.value,
                },
            )
        return self.registry.update_workspace(
            workspace_id,
            status=status,
            metadata=merged_metadata,
            released_at=datetime.now(UTC),
        )

    def _build_workspace_id(
        self,
        *,
        project: str,
        repo: str,
        task_id: str,
        queue_item_id: str,
    ) -> str:
        fingerprint = f"{project}|{repo}|{task_id}|{queue_item_id}"
        return f"workspace-{uuid5(NAMESPACE_URL, fingerprint).hex[:12]}"

    def _build_branch_name(
        self,
        *,
        project: str,
        task_id: str,
        queue_item_id: str,
    ) -> str:
        project_slug = _safe_slug(project)
        task_slug = _safe_slug(task_id)
        queue_slug = _safe_slug(queue_item_id).split("-")[-1]
        return f"lummevia/{project_slug}/{task_slug}-{queue_slug}"

    def _build_worktree_path(
        self,
        *,
        project: str,
        workspace_id: str,
    ) -> str:
        project_slug = _safe_slug(project)
        return str(PurePosixPath(self.workspace_root) / project_slug / workspace_id)


def _safe_slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return normalized or "workspace"
