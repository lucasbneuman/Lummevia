from __future__ import annotations

from pathlib import Path

from lummevia_kilo.schemas import (
    KiloExecutionRequest,
    KiloPreparedWorkspace,
    KiloRuntimeSettings,
)


class KiloWorkspaceManager:
    def __init__(self, settings: KiloRuntimeSettings) -> None:
        self._settings = settings

    def prepare(
        self,
        request: KiloExecutionRequest,
        *,
        execution_id: str,
    ) -> KiloPreparedWorkspace:
        if self._settings.workspace_root is None:
            raise ValueError("KILO_WORKSPACE_ROOT is required for sandbox workspace preparation.")

        workspace_root = self._settings.workspace_root.resolve(strict=False)
        workspace_root.mkdir(parents=True, exist_ok=True)
        workspace_path = (workspace_root / execution_id).resolve(strict=False)
        if workspace_root not in workspace_path.parents and workspace_path != workspace_root:
            raise ValueError("Sandbox workspace path escaped KILO_WORKSPACE_ROOT.")
        workspace_path.mkdir(parents=True, exist_ok=True)

        source_repo_path: Path | None = None
        candidate_repo_path = Path(request.repo_path).resolve(strict=False)
        if candidate_repo_path.exists():
            source_repo_path = candidate_repo_path

        return KiloPreparedWorkspace(
            workspace_path=workspace_path,
            source_repo_path=source_repo_path,
            source_repo_readonly=True,
        )
