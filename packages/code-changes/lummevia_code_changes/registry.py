from __future__ import annotations

from typing import Any, ClassVar

from lummevia_code_changes.schemas import (
    CodeArtifact,
    CodeChangeSet,
    CodeChangeStatus,
    ChangedFile,
)


class CodeChangeRegistry:
    _default_instance: ClassVar["CodeChangeRegistry" | None] = None

    def __init__(self) -> None:
        self._change_sets: dict[str, CodeChangeSet] = {}

    @classmethod
    def default(cls) -> "CodeChangeRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._change_sets.clear()

    def create_change_set(
        self,
        *,
        execution_id: str,
        session_id: str | None,
        task_id: str,
        project: str,
        repo: str,
        workspace_id: str | None,
        files_changed: list[ChangedFile],
        diff_summary: dict[str, Any],
        artifacts: list[CodeArtifact],
        metadata: dict[str, Any] | None = None,
    ) -> CodeChangeSet:
        existing = next(
            (
                change_set
                for change_set in self._change_sets.values()
                if change_set.execution_id == execution_id
                and change_set.session_id == session_id
                and change_set.task_id == task_id
            ),
            None,
        )
        if existing is not None:
            return existing
        change_set = CodeChangeSet(
            execution_id=execution_id,
            session_id=session_id,
            task_id=task_id,
            project=project,
            repo=repo,
            workspace_id=workspace_id,
            files_changed=files_changed,
            diff_summary=diff_summary,
            artifacts=artifacts,
            metadata=metadata or {},
        )
        self._change_sets[change_set.change_set_id] = change_set
        return change_set

    def get_change_set(self, change_set_id: str) -> CodeChangeSet | None:
        return self._change_sets.get(change_set_id)

    def list_change_sets(self) -> list[CodeChangeSet]:
        return sorted(
            self._change_sets.values(),
            key=lambda item: (item.created_at, item.change_set_id),
            reverse=True,
        )

    def update_status(
        self,
        change_set_id: str,
        *,
        status: CodeChangeStatus,
        metadata: dict[str, Any] | None = None,
    ) -> CodeChangeSet:
        change_set = self._change_sets[change_set_id]
        updated = change_set.model_copy(
            update={
                "status": status,
                "metadata": {
                    **change_set.metadata,
                    **(metadata or {}),
                },
            }
        )
        self._change_sets[change_set_id] = updated
        return updated

    def add_artifact(self, change_set_id: str, artifact: CodeArtifact) -> CodeChangeSet:
        change_set = self._change_sets[change_set_id]
        updated = change_set.model_copy(
            update={
                "artifacts": [*change_set.artifacts, artifact],
            }
        )
        self._change_sets[change_set_id] = updated
        return updated
