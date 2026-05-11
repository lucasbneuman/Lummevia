from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from lummevia_kilo.schemas import KiloExecutionRequest, KiloExecutionResult


class KiloExecutionClient:
    """Deterministic fake adapter that simulates a future Kilo CLI boundary."""

    def execute(self, request: KiloExecutionRequest) -> KiloExecutionResult:
        fingerprint = (
            f"{request.run_id}|{request.role.value}|{request.mode.value}|"
            f"{request.project}|{request.repo_path}|{request.task_package.task_id}"
        )
        execution_id = f"kilo-{uuid5(NAMESPACE_URL, fingerprint).hex[:12]}"
        step_name = request.metadata.get("step_name", "kilo_execution")
        duration_ms = 45 + len(request.task_package.expected_artifacts) * 5
        generated_artifacts = [
            {
                "name": artifact_name,
                "kind": "simulated",
                "source": "kilo_adapter_fake",
                "task_id": request.task_package.task_id,
            }
            for artifact_name in request.task_package.expected_artifacts
        ]
        logs = [
            f"[kilo:{request.mode.value.lower()}] accepted task {request.task_package.task_id}",
            f"[kilo:{request.mode.value.lower()}] simulated step {step_name}",
            "[kilo] no real CLI execution was performed",
        ]

        return KiloExecutionResult(
            execution_id=execution_id,
            status="completed",
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
            },
        )
