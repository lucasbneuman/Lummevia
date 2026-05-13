from __future__ import annotations

from typing import Any

from lummevia_code_changes import CodeChangeRegistry
from lummevia_core import AgentRole, TaskPackage
from lummevia_capabilities import AllocationStatus
from lummevia_intelligence import DEFAULT_HIGH_FILES_CHANGED_COUNT
from lummevia_kilo import (
    KiloExecutionClient,
    KiloExecutionRecord,
    KiloExecutionResult,
    build_kilo_execution_request,
    build_planning_task_package,
    resolve_kilo_mode,
)

from lummevia_runtime.capabilities import (
    build_allocation_metadata_for_kilo,
    mark_task_waiting_for_allocation,
    release_step_allocation,
    request_step_allocation,
)
from lummevia_runtime.intelligence import build_execution_context, propose_execution_decision
from lummevia_runtime.planning import build_adaptive_planning_context, propose_adaptive_plan
from lummevia_runtime.sessions import record_kilo_execution_for_session
from lummevia_runtime.state import RuntimeState
from lummevia_runtime.queue import build_queue_metadata_for_kilo
from lummevia_runtime.strategy import resolve_execution_strategy_for_kilo
from lummevia_runtime.supervisor import (
    annotate_kilo_execution_result,
    heartbeat_queue_item_watchdog,
    heartbeat_session_watchdog,
    record_supervisor_event,
    register_kilo_execution_watchdog,
)
from lummevia_supervisor import ExecutionHealthStatus


def build_runtime_planning_task_package(
    *,
    state: RuntimeState,
    task_id: str,
    title: str,
    objective: str,
    prompt: str,
    expected_artifacts: list[str],
    context_refs: list[str] | None = None,
) -> TaskPackage:
    return build_planning_task_package(
        issue_id=state.run.issue_id,
        project=state.run.project,
        task_id=task_id,
        title=title,
        objective=objective,
        prompt=prompt,
        expected_artifacts=expected_artifacts,
        context_refs=context_refs,
    )


def execute_kilo_step(
    state: RuntimeState,
    *,
    step_name: str,
    role: AgentRole,
    task_package: TaskPackage,
    client: KiloExecutionClient,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mode = resolve_kilo_mode(role)
    strategy = resolve_execution_strategy_for_kilo(
        state,
        role=role.value,
        step_name=step_name,
        execution_mode=mode.value,
        sandbox_real=client.settings.enabled and not client.settings.dry_run,
        metadata={"task_id": task_package.task_id},
    )
    session_id = state.metadata.get("current_session_id")
    allocation = request_step_allocation(
        state,
        step_name=step_name,
        role=role,
        mode=mode,
        task_package=task_package,
    )
    if allocation.status != AllocationStatus.GRANTED:
        mark_task_waiting_for_allocation(state, allocation=allocation)
        state.metadata.setdefault("kilo_execution_skipped", {})[step_name] = {
            "task_id": task_package.task_id,
            "role": role.value,
            "mode": mode.value,
            "allocation_id": allocation.allocation_id,
            "allocation_status": allocation.status.value,
            "allocation_reason": allocation.reason,
        }
        return {
            "skipped": True,
            "allocation": allocation.model_dump(mode="json"),
        }
    request = build_kilo_execution_request(
        run_id=state.run.run_id,
        session_id=session_id if isinstance(session_id, str) else None,
        role=role,
        project=state.run.project,
        repo_path=str(state.metadata.get("repo_path", state.run.project)),
        task_package=task_package,
        metadata={
            "step_name": step_name,
            "task_id": task_package.task_id,
            "loop_count": state.loop_count,
            "run_id": state.run.run_id,
            "strategy_id": strategy.strategy_id,
            "strategy_type": strategy.strategy_type.value,
            "risk_level": strategy.risk_level.value,
            "qa_level": strategy.qa_level.value,
            "sandbox_level": strategy.sandbox_level.value,
            "selected_model": strategy.selected_model,
            "selected_provider": strategy.selected_provider,
            "execution_mode": strategy.execution_mode,
            **build_queue_metadata_for_kilo(state, task_package=task_package),
            **build_allocation_metadata_for_kilo(state),
            **(metadata or {}),
        },
    )
    try:
        current_queue_item_id = state.metadata.get("current_queue_item_id")
        if isinstance(current_queue_item_id, str):
            heartbeat_queue_item_watchdog(state, queue_item_id=current_queue_item_id)
        if isinstance(session_id, str):
            heartbeat_session_watchdog(state, session_id=session_id)
        result = client.execute(request)
        record = KiloExecutionRecord(
            execution_id=result.execution_id,
            session_id=request.session_id,
            role=role,
            mode=mode,
            task_id=task_package.task_id,
            status=result.status,
            final_status=result.final_status,
            retry_count=result.retry_count,
            attempts=result.attempts,
            lifecycle=result.lifecycle,
            error=result.error,
        )
        state.kilo_executions.append(record)
        state.metadata.setdefault("kilo_executions", []).append(record.model_dump(mode="json"))
        state.metadata.setdefault("kilo_execution_results", {})[result.execution_id] = (
            result.model_dump(mode="json")
        )
        state.metadata.setdefault("kilo_execution_by_step", {})[step_name] = {
            "execution_id": result.execution_id,
            "session_id": request.session_id,
            "role": role.value,
            "kilo_mode": mode.value,
            "task_id": task_package.task_id,
            "queue_id": result.metadata.get("queue_id"),
            "queue_item_id": result.metadata.get("queue_item_id"),
            "workspace_id": result.metadata.get("workspace_id"),
            "branch_name": result.metadata.get("branch_name"),
            "worktree_path": result.metadata.get("worktree_path"),
            "lock_ids": result.metadata.get("lock_ids", []),
            "workspace_status": result.metadata.get("workspace_status"),
            "allocation_id": result.metadata.get("allocation_id"),
            "allocation_status": result.metadata.get("allocation_status"),
            "capacity_id": result.metadata.get("capacity_id"),
            "capacity_used_slots": result.metadata.get("capacity_used_slots"),
            "capacity_max_slots": result.metadata.get("capacity_max_slots"),
            "allocated_resources": result.metadata.get("allocated_resources", []),
            "allocated_resources_count": result.metadata.get("allocated_resources_count", 0),
            "kilo_status": result.status.value,
            "attempts_count": len(result.attempts),
            "attempts": [attempt.model_dump(mode="json") for attempt in result.attempts],
            "retry_count": result.retry_count,
            "final_status": result.final_status.value,
            "status": result.status.value,
            "strategy_id": result.metadata.get("strategy_id"),
            "strategy_type": result.metadata.get("strategy_type"),
            "risk_level": result.metadata.get("risk_level"),
            "qa_level": result.metadata.get("qa_level"),
            "sandbox_level": result.metadata.get("sandbox_level"),
            "selected_model": result.metadata.get("selected_model"),
            "selected_provider": result.metadata.get("selected_provider"),
            "execution_mode": result.metadata.get("execution_mode"),
            "error": result.error,
            "real_execution": bool(result.metadata.get("real_execution", False)),
            "exit_code": result.metadata.get("exit_code"),
            "safety_status": result.metadata.get("safety_status"),
            "workspace_path": result.metadata.get("workspace_path"),
            "command_preview": result.metadata.get("command_preview"),
            "stdout_bytes": result.metadata.get("stdout_bytes", 0),
            "stderr_bytes": result.metadata.get("stderr_bytes", 0),
            "change_set_id": result.metadata.get("change_set_id"),
            "files_changed_count": result.metadata.get("files_changed_count", 0),
            "lines_added": result.metadata.get("lines_added", 0),
            "lines_removed": result.metadata.get("lines_removed", 0),
            "artifact_count": result.metadata.get("artifact_count", 0),
        }
        change_set_id = result.metadata.get("change_set_id")
        if change_set_id is not None:
            change_set = CodeChangeRegistry.default().get_change_set(str(change_set_id))
            if change_set is not None:
                state.metadata.setdefault("code_change_sets", {})[change_set.change_set_id] = (
                    change_set.model_dump(mode="json")
                )
                state.metadata["last_change_set_id"] = change_set.change_set_id
                state.metadata["files_changed_count"] = change_set.diff_summary.get("files_changed_count", 0)
                state.metadata["lines_added"] = change_set.diff_summary.get("lines_added", 0)
                state.metadata["lines_removed"] = change_set.diff_summary.get("lines_removed", 0)
                state.metadata["artifact_count"] = len(change_set.artifacts)
                if role == AgentRole.DEV:
                    state.metadata.setdefault("task_change_set_ids", {})[task_package.task_id] = (
                        change_set.change_set_id
                    )
                    state.metadata["current_change_set_id"] = change_set.change_set_id
                record_supervisor_event(
                    state,
                    event_type="CODE_CHANGE_DETECTED",
                    status=ExecutionHealthStatus.HEALTHY,
                    metadata={
                        "change_set_id": change_set.change_set_id,
                        "execution_id": result.execution_id,
                        "task_id": task_package.task_id,
                        "files_changed_count": change_set.diff_summary.get("files_changed_count", 0),
                        "lines_added": change_set.diff_summary.get("lines_added", 0),
                        "lines_removed": change_set.diff_summary.get("lines_removed", 0),
                        "artifact_count": len(change_set.artifacts),
                    },
                )
                if change_set.diff_summary.get("files_changed_count", 0) >= DEFAULT_HIGH_FILES_CHANGED_COUNT:
                    propose_execution_decision(
                        state,
                        context=build_execution_context(
                            state,
                            task_id=task_package.task_id,
                            files_changed_count=int(change_set.diff_summary.get("files_changed_count", 0)),
                            real_code_touched=role == AgentRole.DEV,
                            metadata={
                                "source": "code_change_detection",
                                "change_set_id": change_set.change_set_id,
                                "execution_id": result.execution_id,
                            },
                        ),
                    )
                    propose_adaptive_plan(
                        state,
                        context=build_adaptive_planning_context(
                            state,
                            trigger_reason="large_diff",
                            source_task_id=task_package.task_id,
                            files_changed_count=int(change_set.diff_summary.get("files_changed_count", 0)),
                            metadata={
                                "source": "code_change_detection",
                                "change_set_id": change_set.change_set_id,
                                "execution_id": result.execution_id,
                            },
                        ),
                    )
        health_status = (
            ExecutionHealthStatus.HEALTHY
            if result.final_status.value == "SUCCESS"
            else ExecutionHealthStatus.FAILED
        )
        watchdog_id = register_kilo_execution_watchdog(
            state,
            execution_id=result.execution_id,
            step_name=step_name,
            task_id=task_package.task_id,
            retry_attempts=result.retry_count,
            health_status=health_status,
        )
        state.metadata["kilo_execution_results"][result.execution_id]["metadata"]["watchdog_id"] = watchdog_id
        state.metadata["kilo_execution_results"][result.execution_id]["metadata"]["health_status"] = health_status.value
        state.metadata["kilo_execution_results"][result.execution_id]["metadata"]["retry_attempts"] = result.retry_count
        state.metadata["kilo_execution_by_step"][step_name]["watchdog_id"] = watchdog_id
        state.metadata["kilo_execution_by_step"][step_name]["health_status"] = health_status.value
        state.metadata["kilo_execution_by_step"][step_name]["retry_attempts"] = result.retry_count
        annotate_kilo_execution_result(
            state,
            step_name=step_name,
            result_metadata={"watchdog_id": watchdog_id},
            retry_attempts=result.retry_count,
            health_status=health_status,
        )
        if health_status == ExecutionHealthStatus.FAILED:
            propose_execution_decision(
                state,
                context=build_execution_context(
                    state,
                    task_id=task_package.task_id,
                    retry_count=result.retry_count,
                    max_retries=max(1, int(result.metadata.get("max_attempts", 1)) - 1),
                    kilo_failed=True,
                    real_code_touched=role == AgentRole.DEV,
                    metadata={
                        "source": "kilo_execution",
                        "step_name": step_name,
                        "execution_id": result.execution_id,
                        "final_status": result.final_status.value,
                    },
                ),
            )
        if request.session_id is not None:
            record_kilo_execution_for_session(
                state,
                step_name=step_name,
                role=role,
                mode=mode,
                result=KiloExecutionResult.model_validate(result.model_dump(mode="json")),
            )
        return result.model_dump(mode="json")
    finally:
        release_step_allocation(state, allocation_id=allocation.allocation_id)
