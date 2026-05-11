from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from lummevia_kilo.schemas import (
    KiloExecutionAttempt,
    KiloExecutionRequest,
    KiloExecutionResult,
    KiloExecutionStatus,
)


class KiloExecutionClient:
    """Deterministic fake adapter that simulates a future Kilo CLI boundary."""

    def execute(self, request: KiloExecutionRequest) -> KiloExecutionResult:
        fingerprint = (
            f"{request.run_id}|{request.role.value}|{request.mode.value}|"
            f"{request.project}|{request.repo_path}|{request.task_package.task_id}"
        )
        execution_id = f"kilo-{uuid5(NAMESPACE_URL, fingerprint).hex[:12]}"
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

        return KiloExecutionResult(
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
