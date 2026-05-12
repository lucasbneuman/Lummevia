from __future__ import annotations

from pathlib import Path

from lummevia_kilo.exceptions import KiloSafetyViolation
from lummevia_kilo.schemas import (
    KiloExecutionRequest,
    KiloRuntimeSettings,
    KiloSafetyCheckResult,
)


class KiloSafetyValidator:
    def __init__(self, settings: KiloRuntimeSettings) -> None:
        self._settings = settings

    def validate(self, request: KiloExecutionRequest) -> KiloSafetyCheckResult:
        repo_name = (request.task_package.target_repo or request.project).strip()

        if not self._settings.enabled:
            return KiloSafetyCheckResult(
                allowed=False,
                status="DISABLED",
                reason="Real Kilo execution is disabled by KILO_ENABLED=false.",
                repo_name=repo_name,
                workspace_root=self._workspace_root_as_str(),
            )

        if self._settings.dry_run:
            return KiloSafetyCheckResult(
                allowed=False,
                status="DRY_RUN",
                reason="Real Kilo execution is blocked while KILO_DRY_RUN=true.",
                repo_name=repo_name,
                workspace_root=self._workspace_root_as_str(),
            )

        if repo_name not in self._settings.allowed_repos:
            return KiloSafetyCheckResult(
                allowed=False,
                status="BLOCKED",
                reason=f"Repo '{repo_name}' is not present in KILO_ALLOWED_REPOS allowlist.",
                repo_name=repo_name,
                workspace_root=self._workspace_root_as_str(),
            )

        if self._settings.workspace_root is None:
            return KiloSafetyCheckResult(
                allowed=False,
                status="BLOCKED",
                reason="KILO_WORKSPACE_ROOT must be configured for real execution.",
                repo_name=repo_name,
            )
        execution_id = str(request.metadata.get("execution_id", "")).strip()
        if execution_id and ("/" in execution_id or "\\" in execution_id or ".." in execution_id):
            return KiloSafetyCheckResult(
                allowed=False,
                status="BLOCKED",
                reason="Sandbox execution_id would escape KILO_WORKSPACE_ROOT.",
                repo_name=repo_name,
                workspace_root=self._workspace_root_as_str(),
            )

        try:
            normalized_repo_path = self._normalize_repo_path(request.repo_path)
        except ValueError as exc:
            return KiloSafetyCheckResult(
                allowed=False,
                status="BLOCKED",
                reason=str(exc),
                repo_name=repo_name,
                workspace_root=self._workspace_root_as_str(),
            )

        return KiloSafetyCheckResult(
            allowed=True,
            status="ALLOWED",
            repo_name=repo_name,
            normalized_repo_path=str(normalized_repo_path),
            workspace_root=self._workspace_root_as_str(),
        )

    def ensure_allowed(self, request: KiloExecutionRequest) -> KiloSafetyCheckResult:
        result = self.validate(request)
        if not result.allowed:
            raise KiloSafetyViolation(result)
        return result

    def _normalize_repo_path(self, repo_path: str) -> Path:
        raw = Path(repo_path)
        if any(part == ".." for part in raw.parts):
            raise ValueError("Repo path traversal is not allowed for sandbox execution.")
        return raw.resolve(strict=False)

    def _workspace_root_as_str(self) -> str | None:
        if self._settings.workspace_root is None:
            return None
        return str(self._settings.workspace_root.resolve(strict=False))
