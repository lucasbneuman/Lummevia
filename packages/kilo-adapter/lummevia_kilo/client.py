from __future__ import annotations

import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from lummevia_code_changes import (
    CodeArtifact,
    CodeChangeRegistry,
    WorkspaceSnapshot,
    capture_workspace_snapshot,
    compare_workspace_snapshots,
    create_simulated_artifact,
)
from lummevia_kilo.exceptions import KiloSafetyViolation
from lummevia_kilo.safety import KiloSafetyValidator
from lummevia_kilo.schemas import (
    KiloExecutionAttempt,
    KiloExecutionRequest,
    KiloExecutionResult,
    KiloExecutionStatus,
    KiloRuntimeSettings,
    KiloSubprocessResult,
)
from lummevia_kilo.subprocess_executor import ControlledSubprocessExecutor


class KiloExecutionClient:
    """Fake-first Kilo adapter with an opt-in controlled subprocess path."""

    def __init__(
        self,
        *,
        settings: KiloRuntimeSettings | None = None,
        subprocess_executor: ControlledSubprocessExecutor | None = None,
    ) -> None:
        self.settings = settings or load_kilo_runtime_settings()
        self.safety_validator = KiloSafetyValidator(self.settings)
        self.subprocess_executor = subprocess_executor or ControlledSubprocessExecutor(
            settings=self.settings,
            safety_validator=self.safety_validator,
        )

    def execute(self, request: KiloExecutionRequest) -> KiloExecutionResult:
        execution_id = self._build_execution_id(request)
        before_snapshot = self._capture_before_snapshot(
            request=request,
            execution_id=execution_id,
        )
        request = request.model_copy(
            update={
                "metadata": {
                    **request.metadata,
                    "execution_id": execution_id,
                }
            }
        )

        if not self.settings.enabled:
            return self._execute_fake(
                request,
                execution_id=execution_id,
                safety_status="DISABLED",
                before_snapshot=before_snapshot,
            )
        if self.settings.dry_run:
            return self._execute_fake(
                request,
                execution_id=execution_id,
                safety_status="DRY_RUN",
                before_snapshot=before_snapshot,
            )
        return self._execute_real(
            request,
            execution_id=execution_id,
            before_snapshot=before_snapshot,
        )

    def _execute_fake(
        self,
        request: KiloExecutionRequest,
        *,
        execution_id: str,
        safety_status: str,
        before_snapshot: WorkspaceSnapshot,
    ) -> KiloExecutionResult:
        step_name = request.metadata.get("step_name", "kilo_execution")
        logs = [
            f"[kilo:{request.mode.value.lower()}] accepted task {request.task_package.task_id}",
            f"[kilo:{request.mode.value.lower()}] simulated step {step_name}",
            "[kilo] no real CLI execution was performed",
        ]
        lifecycle = [
            KiloExecutionStatus.QUEUED,
            KiloExecutionStatus.RUNNING,
        ]
        attempts: list[KiloExecutionAttempt] = []
        max_attempts = int(request.metadata.get("max_attempts", request.retry_policy.max_attempts))
        fail_first_attempt = bool(request.metadata.get("fail_first_attempt", False))
        error: str | None = None
        final_status = KiloExecutionStatus.SUCCESS

        for attempt_number in range(1, max_attempts + 1):
            if attempt_number == 1 and fail_first_attempt:
                error = f"Simulated failure on attempt {attempt_number}."
                attempts.append(
                    KiloExecutionAttempt(
                        attempt_number=attempt_number,
                        status=KiloExecutionStatus.FAILED,
                        error=error,
                    )
                )
                lifecycle.append(KiloExecutionStatus.FAILED)
                logs.append(
                    f"[kilo:{request.mode.value.lower()}] attempt {attempt_number} failed"
                )
                if attempt_number < max_attempts:
                    lifecycle.extend(
                        [
                            KiloExecutionStatus.RETRYING,
                            KiloExecutionStatus.RUNNING,
                        ]
                    )
                    logs.append(
                        f"[kilo:{request.mode.value.lower()}] retrying task "
                        f"{request.task_package.task_id}"
                    )
                    continue
                final_status = KiloExecutionStatus.FAILED
                break

            attempts.append(
                KiloExecutionAttempt(
                    attempt_number=attempt_number,
                    status=KiloExecutionStatus.SUCCESS,
                )
            )
            lifecycle.append(KiloExecutionStatus.SUCCESS)
            final_status = KiloExecutionStatus.SUCCESS
            error = None
            break

        generated_artifacts = (
            [
                {
                    "name": artifact_name,
                    "kind": "simulated",
                    "source": "kilo_adapter_fake",
                    "task_id": request.task_package.task_id,
                }
                for artifact_name in request.task_package.expected_artifacts
            ]
            if final_status == KiloExecutionStatus.SUCCESS
            else []
        )
        duration_ms = 45 + len(request.task_package.expected_artifacts) * 5 + (
            max(0, len(attempts) - 1) * 20
        )
        retry_count = max(0, len(attempts) - 1)

        result = KiloExecutionResult(
            execution_id=execution_id,
            role=request.role,
            mode=request.mode,
            task_id=request.task_package.task_id,
            status=final_status,
            final_status=final_status,
            retry_count=retry_count,
            attempts=attempts,
            lifecycle=lifecycle,
            error=error,
            summary=(
                f"Simulated {request.mode.value.lower()} execution for "
                f"{request.role.value} on task {request.task_package.task_id}."
            ),
            generated_artifacts=generated_artifacts,
            logs=logs,
            duration_ms=duration_ms,
            metadata={
                **request.metadata,
                "adapter": "kilo_fake",
                "execution_layer": "kilo_adapter",
                "real_execution": False,
                "exit_code": None,
                "stdout_preview": "",
                "stderr_preview": "",
                "workspace_path": request.metadata.get("worktree_path"),
                "command_preview": "",
                "safety_status": safety_status,
                "stdout_bytes": 0,
                "stderr_bytes": 0,
                "role": request.role.value,
                "mode": request.mode.value,
                "task_id": request.task_package.task_id,
                "repo_path": request.repo_path,
                "max_attempts": max_attempts,
                "attempts_count": len(attempts),
                "retry_count": retry_count,
                "final_status": final_status.value,
                "lifecycle": [status.value for status in lifecycle],
            },
        )
        return self._attach_change_set(
            request,
            result=result,
            workspace_path=request.metadata.get("worktree_path"),
            artifacts=self._build_simulated_artifacts(
                request=request,
                generated_artifacts=generated_artifacts,
            ),
            before_snapshot=before_snapshot,
        )

    def _execute_real(
        self,
        request: KiloExecutionRequest,
        *,
        execution_id: str,
        before_snapshot: WorkspaceSnapshot,
    ) -> KiloExecutionResult:
        max_attempts = int(request.metadata.get("max_attempts", request.retry_policy.max_attempts))
        safety = self.safety_validator.validate(request)
        lifecycle = [KiloExecutionStatus.QUEUED, KiloExecutionStatus.RUNNING]
        logs = [f"[kilo:{request.mode.value.lower()}] real sandbox execution requested"]
        attempts: list[KiloExecutionAttempt] = []
        error: str | None = None
        last_subprocess: KiloSubprocessResult | None = None

        if not safety.allowed:
            lifecycle.append(KiloExecutionStatus.FAILED)
            return KiloExecutionResult(
                execution_id=execution_id,
                role=request.role,
                mode=request.mode,
                task_id=request.task_package.task_id,
                status=KiloExecutionStatus.FAILED,
                final_status=KiloExecutionStatus.FAILED,
                retry_count=0,
                attempts=[],
                lifecycle=lifecycle,
                error=safety.reason,
                summary=(
                    f"Blocked real {request.mode.value.lower()} execution for "
                    f"{request.role.value} on task {request.task_package.task_id}."
                ),
                generated_artifacts=[],
                logs=[*logs, f"[kilo] blocked by safety: {safety.status}"],
                duration_ms=0,
                metadata={
                    **request.metadata,
                    "adapter": "kilo_real",
                    "execution_layer": "kilo_adapter",
                    "real_execution": False,
                    "exit_code": None,
                    "stdout_preview": "",
                    "stderr_preview": "",
                    "workspace_path": None,
                    "command_preview": "",
                    "safety_status": safety.status,
                    "stdout_bytes": 0,
                    "stderr_bytes": 0,
                },
            )

        for attempt_number in range(1, max_attempts + 1):
            try:
                last_subprocess = self.subprocess_executor.execute(request)
            except KiloSafetyViolation as exc:
                error = exc.result.reason
                attempts.append(
                    KiloExecutionAttempt(
                        attempt_number=attempt_number,
                        status=KiloExecutionStatus.FAILED,
                        error=error,
                    )
                )
                lifecycle.append(KiloExecutionStatus.FAILED)
                break

            if last_subprocess.exit_code == 0 and not last_subprocess.timed_out:
                attempts.append(
                    KiloExecutionAttempt(
                        attempt_number=attempt_number,
                        status=KiloExecutionStatus.SUCCESS,
                    )
                )
                lifecycle.append(KiloExecutionStatus.SUCCESS)
                error = None
                break

            error = last_subprocess.stderr_preview or (
                f"Kilo CLI exited with code {last_subprocess.exit_code}."
            )
            attempts.append(
                KiloExecutionAttempt(
                    attempt_number=attempt_number,
                    status=KiloExecutionStatus.FAILED,
                    error=error,
                )
            )
            lifecycle.append(KiloExecutionStatus.FAILED)
            if attempt_number < max_attempts:
                lifecycle.extend([KiloExecutionStatus.RETRYING, KiloExecutionStatus.RUNNING])
                logs.append(
                    f"[kilo:{request.mode.value.lower()}] retrying task {request.task_package.task_id}"
                )

        final_status = attempts[-1].status if attempts else KiloExecutionStatus.FAILED
        retry_count = max(0, len(attempts) - 1)
        result = KiloExecutionResult(
            execution_id=execution_id,
            role=request.role,
            mode=request.mode,
            task_id=request.task_package.task_id,
            status=final_status,
            final_status=final_status,
            retry_count=retry_count,
            attempts=attempts,
            lifecycle=lifecycle,
            error=error,
            summary=(
                f"Real sandbox {request.mode.value.lower()} execution for "
                f"{request.role.value} on task {request.task_package.task_id} "
                f"{'completed successfully' if final_status == KiloExecutionStatus.SUCCESS else 'failed'}."
            ),
            generated_artifacts=(
                [
                    {
                        "name": artifact_name,
                        "kind": "sandbox",
                        "source": "kilo_adapter_real",
                        "task_id": request.task_package.task_id,
                    }
                    for artifact_name in request.task_package.expected_artifacts
                ]
                if final_status == KiloExecutionStatus.SUCCESS
                else []
            ),
            logs=logs,
            duration_ms=0 if last_subprocess is None else last_subprocess.duration_ms,
            metadata={
                **request.metadata,
                "adapter": "kilo_real",
                "execution_layer": "kilo_adapter",
                "real_execution": final_status == KiloExecutionStatus.SUCCESS,
                "exit_code": None if last_subprocess is None else last_subprocess.exit_code,
                "stdout_preview": "" if last_subprocess is None else last_subprocess.stdout_preview,
                "stderr_preview": "" if last_subprocess is None else last_subprocess.stderr_preview,
                "workspace_path": None if last_subprocess is None else last_subprocess.workspace_path,
                "command_preview": "" if last_subprocess is None else last_subprocess.command_preview,
                "safety_status": safety.status,
                "stdout_bytes": 0 if last_subprocess is None else last_subprocess.stdout_bytes,
                "stderr_bytes": 0 if last_subprocess is None else last_subprocess.stderr_bytes,
                "role": request.role.value,
                "mode": request.mode.value,
                "task_id": request.task_package.task_id,
                "repo_path": request.repo_path,
                "max_attempts": max_attempts,
                "attempts_count": len(attempts),
                "retry_count": retry_count,
                "final_status": final_status.value,
                "lifecycle": [status.value for status in lifecycle],
            },
        )
        return self._attach_change_set(
            request,
            result=result,
            workspace_path=None if last_subprocess is None else last_subprocess.workspace_path,
            artifacts=self._build_simulated_artifacts(request=request, result=result),
            before_snapshot=before_snapshot,
        )

    def _build_execution_id(self, request: KiloExecutionRequest) -> str:
        fingerprint = (
            f"{request.run_id}|{request.role.value}|{request.mode.value}|"
            f"{request.project}|{request.repo_path}|{request.task_package.task_id}"
        )
        return f"kilo-{uuid5(NAMESPACE_URL, fingerprint).hex[:12]}"

    def _attach_change_set(
        self,
        request: KiloExecutionRequest,
        *,
        result: KiloExecutionResult,
        workspace_path: str | None,
        artifacts: list[CodeArtifact],
        before_snapshot: WorkspaceSnapshot,
    ) -> KiloExecutionResult:
        after_snapshot = capture_workspace_snapshot(workspace_path or "<missing-workspace>")
        diff_result = compare_workspace_snapshots(
            before=before_snapshot,
            after=after_snapshot,
        )
        change_set = CodeChangeRegistry.default().create_change_set(
            execution_id=result.execution_id,
            session_id=request.session_id,
            task_id=request.task_package.task_id,
            project=request.project,
            repo=request.task_package.target_repo or request.project,
            workspace_id=(
                str(request.metadata.get("workspace_id"))
                if request.metadata.get("workspace_id")
                else None
            ),
            files_changed=diff_result.files_changed,
            diff_summary=diff_result.diff_summary,
            artifacts=artifacts,
            metadata={
                "run_id": request.run_id,
                "workspace_path": workspace_path,
                "real_execution": result.metadata.get("real_execution", False),
                "validation_status": "PENDING",
                "validation_notes": None,
                "qa_checked_change_set_id": None,
            },
        )
        return result.model_copy(
            update={
                "metadata": {
                    **result.metadata,
                    "change_set_id": change_set.change_set_id,
                    "change_set": change_set.model_dump(mode="json"),
                    "files_changed_count": change_set.diff_summary.get("files_changed_count", 0),
                    "lines_added": change_set.diff_summary.get("lines_added", 0),
                    "lines_removed": change_set.diff_summary.get("lines_removed", 0),
                    "artifact_count": len(change_set.artifacts),
                }
            }
        )

    def _capture_before_snapshot(
        self,
        *,
        request: KiloExecutionRequest,
        execution_id: str,
    ) -> WorkspaceSnapshot:
        workspace_path = self._resolve_workspace_path(
            request=request,
            execution_id=execution_id,
        )
        return capture_workspace_snapshot(workspace_path or "<missing-workspace>")

    def _resolve_workspace_path(
        self,
        *,
        request: KiloExecutionRequest,
        execution_id: str,
    ) -> str | None:
        worktree_path = request.metadata.get("worktree_path")
        if isinstance(worktree_path, str) and worktree_path.strip():
            return worktree_path
        if self.settings.workspace_root is None:
            return None
        return str((self.settings.workspace_root.resolve(strict=False) / execution_id).resolve(strict=False))

    def _build_simulated_artifacts(
        self,
        *,
        request: KiloExecutionRequest,
        result: KiloExecutionResult | None = None,
        generated_artifacts: list[dict[str, object]] | None = None,
    ) -> list[CodeArtifact]:
        artifact_payloads = generated_artifacts or (
            result.generated_artifacts if result is not None else []
        )
        if not artifact_payloads:
            return [
                create_simulated_artifact(
                    artifact_type="execution_summary",
                    path=f"simulated://{request.task_package.task_id}/summary",
                    content_hint=request.task_package.prompt,
                    metadata={"simulated": True},
                )
            ]
        artifacts: list[CodeArtifact] = []
        for payload in artifact_payloads:
            artifact_name = str(payload.get("name", "artifact"))
            artifacts.append(
                create_simulated_artifact(
                    artifact_type=str(payload.get("kind", "simulated")),
                    path=f"simulated://{request.task_package.task_id}/{artifact_name}",
                    content_hint=artifact_name,
                    metadata={"simulated": True, **payload},
                )
            )
        return artifacts


def load_kilo_runtime_settings() -> KiloRuntimeSettings:
    return KiloRuntimeSettings(
        enabled=_read_bool("KILO_ENABLED", False),
        dry_run=_read_bool("KILO_DRY_RUN", True),
        cli_path=_read_optional_path("KILO_CLI_PATH"),
        workspace_root=_read_optional_path("KILO_WORKSPACE_ROOT"),
        default_timeout_seconds=_read_int("KILO_DEFAULT_TIMEOUT_SECONDS", 300),
        allowed_repos=_read_csv("KILO_ALLOWED_REPOS"),
        max_output_bytes=_read_int("KILO_MAX_OUTPUT_BYTES", 32768),
    )


def _read_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None or not value.strip():
        return default
    return int(value.strip())


def _read_csv(key: str) -> tuple[str, ...]:
    value = os.getenv(key, "")
    parts = [item.strip() for item in value.split(",")]
    return tuple(item for item in parts if item)


def _read_optional_path(key: str) -> Path | None:
    value = os.getenv(key)
    if value is None or not value.strip():
        return None
    return Path(value.strip()).expanduser()
