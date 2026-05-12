from __future__ import annotations

import shlex
import subprocess
from time import perf_counter

from lummevia_kilo.safety import KiloSafetyValidator
from lummevia_kilo.schemas import (
    KiloExecutionRequest,
    KiloRuntimeSettings,
    KiloSubprocessResult,
)
from lummevia_kilo.workspace import KiloWorkspaceManager


class ControlledSubprocessExecutor:
    def __init__(
        self,
        *,
        settings: KiloRuntimeSettings,
        safety_validator: KiloSafetyValidator | None = None,
        workspace_manager: KiloWorkspaceManager | None = None,
    ) -> None:
        self._settings = settings
        self._safety_validator = safety_validator or KiloSafetyValidator(settings)
        self._workspace_manager = workspace_manager or KiloWorkspaceManager(settings)

    def execute(self, request: KiloExecutionRequest) -> KiloSubprocessResult:
        self._safety_validator.ensure_allowed(request)

        execution_id = request.metadata.get("execution_id")
        if not isinstance(execution_id, str) or not execution_id.strip():
            execution_id = f"sandbox-{request.task_package.task_id.casefold().replace('/', '-')}"

        workspace = self._workspace_manager.prepare(request, execution_id=execution_id)
        command = self._build_command(request, workspace_path=str(workspace.workspace_path))
        command_preview = " ".join(shlex.quote(part) for part in command)
        timeout = int(request.metadata.get("timeout_seconds", self._settings.default_timeout_seconds))
        started = perf_counter()

        try:
            completed = subprocess.run(
                args=command,
                cwd=str(workspace.workspace_path),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired:
            duration_ms = int((perf_counter() - started) * 1000)
            timeout_message = f"Kilo CLI timed out after {timeout} seconds."
            return KiloSubprocessResult(
                exit_code=-1,
                stdout_preview="",
                stderr_preview=timeout_message,
                stdout_bytes=0,
                stderr_bytes=len(timeout_message.encode("utf-8")),
                duration_ms=duration_ms,
                timed_out=True,
                command_preview=command_preview,
                workspace_path=str(workspace.workspace_path),
            )

        duration_ms = int((perf_counter() - started) * 1000)
        stdout_preview, stdout_bytes = _truncate_output(
            completed.stdout or "",
            max_bytes=self._settings.max_output_bytes,
        )
        stderr_preview, stderr_bytes = _truncate_output(
            completed.stderr or "",
            max_bytes=self._settings.max_output_bytes,
        )
        return KiloSubprocessResult(
            exit_code=int(completed.returncode),
            stdout_preview=stdout_preview,
            stderr_preview=stderr_preview,
            stdout_bytes=stdout_bytes,
            stderr_bytes=stderr_bytes,
            duration_ms=duration_ms,
            timed_out=False,
            command_preview=command_preview,
            workspace_path=str(workspace.workspace_path),
        )

    def _build_command(self, request: KiloExecutionRequest, *, workspace_path: str) -> list[str]:
        if self._settings.cli_path is None:
            raise ValueError("KILO_CLI_PATH is required for real sandbox execution.")

        return [
            str(self._settings.cli_path),
            "--mode",
            request.mode.value.lower(),
            "--project",
            request.project,
            "--task-id",
            request.task_package.task_id,
            "--workspace",
            workspace_path,
            "--prompt",
            request.task_package.prompt,
        ]


def _truncate_output(value: str, *, max_bytes: int) -> tuple[str, int]:
    encoded = value.encode("utf-8")
    total_bytes = len(encoded)
    if total_bytes <= max_bytes:
        return value, total_bytes
    truncated = encoded[: max(0, max_bytes - 3)].decode("utf-8", errors="ignore")
    return f"{truncated}...", total_bytes
