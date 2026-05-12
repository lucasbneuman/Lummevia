from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from lummevia_queue import TaskQueueRegistry, TaskQueueStatus
from lummevia_sessions import SessionRegistry
from lummevia_supervisor import ExecutionHealthStatus, SupervisorRegistry, WatchdogStatus

from lummevia_runtime.intelligence import build_execution_context, propose_execution_decision
from lummevia_runtime.planning import build_adaptive_planning_context, propose_adaptive_plan
from lummevia_runtime.state import RuntimeState
from lummevia_runtime.timeline import sync_timeline_for_state


def initialize_supervisor_runtime_state(state: RuntimeState) -> None:
    state.metadata.setdefault("health_status", ExecutionHealthStatus.WAITING.value)
    state.metadata.setdefault("retry_attempts", 0)
    state.metadata.setdefault("stuck_detected", False)
    state.metadata.setdefault("workflow_cancelled", False)
    SupervisorRegistry.default()._sync_runtime_metadata(state)


def record_supervisor_event(
    state: RuntimeState,
    *,
    event_type: str,
    status: ExecutionHealthStatus,
    metadata: dict[str, Any] | None = None,
    session_id: str | None = None,
    queue_item_id: str | None = None,
) -> None:
    registry = SupervisorRegistry.default()
    registry.create_supervisor_event(
        workflow_run_id=state.run.run_id,
        session_id=session_id or _current_session_id(state),
        queue_item_id=queue_item_id or _current_queue_item_id(state),
        event_type=event_type,
        status=status,
        metadata=metadata or {},
    )
    registry._sync_runtime_metadata(state)
    sync_timeline_for_state(state)


def register_queue_item_watchdog(
    state: RuntimeState,
    *,
    queue_id: str,
    queue_item_id: str,
    task_id: str,
    timeout_seconds: int = 300,
) -> str:
    watchdog = SupervisorRegistry.default().register_watchdog(
        workflow_run_id=state.run.run_id,
        target_type="TaskQueueItem",
        target_id=queue_item_id,
        timeout_seconds=timeout_seconds,
        metadata={
            "queue_id": queue_id,
            "queue_item_id": queue_item_id,
            "task_id": task_id,
            "retry_attempts": 0,
            "max_retries": 1,
        },
    )
    _sync_queue_item_health(
        state,
        queue_item_id=queue_item_id,
        health_status=ExecutionHealthStatus.RUNNING,
        watchdog_id=watchdog.watchdog_id,
        last_heartbeat_at=watchdog.last_heartbeat_at,
    )
    record_supervisor_event(
        state,
        event_type="WATCHDOG_CREATED",
        status=ExecutionHealthStatus.RUNNING,
        metadata={
            "watchdog_id": watchdog.watchdog_id,
            "target_type": "TaskQueueItem",
            "target_id": queue_item_id,
            "task_id": task_id,
        },
        queue_item_id=queue_item_id,
    )
    return watchdog.watchdog_id


def heartbeat_queue_item_watchdog(state: RuntimeState, *, queue_item_id: str) -> None:
    watchdog = _find_watchdog(state.run.run_id, "TaskQueueItem", queue_item_id)
    if watchdog is None:
        return
    updated = SupervisorRegistry.default().heartbeat(watchdog.watchdog_id)
    _sync_queue_item_health(
        state,
        queue_item_id=queue_item_id,
        health_status=ExecutionHealthStatus.RUNNING,
        watchdog_id=updated.watchdog_id,
        last_heartbeat_at=updated.last_heartbeat_at,
    )
    SupervisorRegistry.default()._sync_runtime_metadata(state)


def complete_queue_item_watchdog(state: RuntimeState, *, queue_item_id: str) -> None:
    watchdog = _find_watchdog(state.run.run_id, "TaskQueueItem", queue_item_id)
    if watchdog is None:
        return
    SupervisorRegistry.default().save_watchdog(
        watchdog.model_copy(update={"status": WatchdogStatus.COMPLETED})
    )
    _sync_queue_item_health(
        state,
        queue_item_id=queue_item_id,
        health_status=ExecutionHealthStatus.HEALTHY,
        watchdog_id=watchdog.watchdog_id,
        last_heartbeat_at=datetime.now(UTC),
    )
    SupervisorRegistry.default()._sync_runtime_metadata(state)


def register_session_watchdog(
    state: RuntimeState,
    *,
    session_id: str,
    task_id: str,
    timeout_seconds: int = 300,
) -> str:
    watchdog = SupervisorRegistry.default().register_watchdog(
        workflow_run_id=state.run.run_id,
        target_type="TaskExecutionSession",
        target_id=session_id,
        timeout_seconds=timeout_seconds,
        metadata={
            "session_id": session_id,
            "queue_item_id": _current_queue_item_id(state),
            "task_id": task_id,
            "retry_attempts": 0,
            "max_retries": 1,
        },
    )
    session = SessionRegistry.default().get_session(session_id)
    if session is not None:
        SessionRegistry.default().save_session(
            session.model_copy(
                update={
                    "watchdog_id": watchdog.watchdog_id,
                    "health_status": ExecutionHealthStatus.RUNNING.value,
                    "metadata": {
                        **session.metadata,
                        "watchdog_id": watchdog.watchdog_id,
                        "health_status": ExecutionHealthStatus.RUNNING.value,
                    },
                }
            )
        )
        state.metadata.setdefault("sessions", {})[session_id] = (
            SessionRegistry.default().get_session(session_id).model_dump(mode="json")
        )
    state.metadata["health_status"] = ExecutionHealthStatus.RUNNING.value
    state.metadata["watchdog_id"] = watchdog.watchdog_id
    record_supervisor_event(
        state,
        event_type="WATCHDOG_CREATED",
        status=ExecutionHealthStatus.RUNNING,
        metadata={
            "watchdog_id": watchdog.watchdog_id,
            "target_type": "TaskExecutionSession",
            "target_id": session_id,
            "task_id": task_id,
        },
        session_id=session_id,
    )
    return watchdog.watchdog_id


def heartbeat_session_watchdog(state: RuntimeState, *, session_id: str) -> None:
    watchdog = _find_watchdog(state.run.run_id, "TaskExecutionSession", session_id)
    if watchdog is None:
        return
    updated = SupervisorRegistry.default().heartbeat(watchdog.watchdog_id)
    session = SessionRegistry.default().get_session(session_id)
    if session is not None:
        SessionRegistry.default().save_session(
            session.model_copy(
                update={
                    "health_status": ExecutionHealthStatus.RUNNING.value,
                    "metadata": {
                        **session.metadata,
                        "health_status": ExecutionHealthStatus.RUNNING.value,
                        "last_heartbeat_at": updated.last_heartbeat_at.isoformat(),
                    },
                }
            )
        )
        state.metadata.setdefault("sessions", {})[session_id] = (
            SessionRegistry.default().get_session(session_id).model_dump(mode="json")
        )
    state.metadata["watchdog_id"] = updated.watchdog_id
    state.metadata["last_heartbeat_at"] = updated.last_heartbeat_at.isoformat()
    SupervisorRegistry.default()._sync_runtime_metadata(state)


def finalize_session_health(
    state: RuntimeState,
    *,
    session_id: str,
    health_status: ExecutionHealthStatus,
) -> None:
    watchdog = _find_watchdog(state.run.run_id, "TaskExecutionSession", session_id)
    if watchdog is not None:
        SupervisorRegistry.default().save_watchdog(
            watchdog.model_copy(update={"status": WatchdogStatus.COMPLETED})
        )
    session = SessionRegistry.default().get_session(session_id)
    if session is not None:
        SessionRegistry.default().save_session(
            session.model_copy(
                update={
                    "health_status": health_status.value,
                    "metadata": {
                        **session.metadata,
                        "health_status": health_status.value,
                    },
                }
            )
        )
        state.metadata.setdefault("sessions", {})[session_id] = (
            SessionRegistry.default().get_session(session_id).model_dump(mode="json")
        )
    state.metadata["health_status"] = health_status.value
    SupervisorRegistry.default()._sync_runtime_metadata(state)


def register_kilo_execution_watchdog(
    state: RuntimeState,
    *,
    execution_id: str,
    step_name: str,
    task_id: str,
    retry_attempts: int,
    health_status: ExecutionHealthStatus,
) -> str:
    watchdog = SupervisorRegistry.default().register_watchdog(
        workflow_run_id=state.run.run_id,
        target_type="KiloExecution",
        target_id=execution_id,
        timeout_seconds=300,
        metadata={
            "execution_id": execution_id,
            "session_id": _current_session_id(state),
            "queue_item_id": _current_queue_item_id(state),
            "task_id": task_id,
            "step_name": step_name,
            "retry_attempts": retry_attempts,
            "max_retries": 1,
        },
    )
    state.metadata.setdefault("kilo_execution_by_step", {}).setdefault(step_name, {})
    state.metadata["kilo_execution_by_step"][step_name]["watchdog_id"] = watchdog.watchdog_id
    state.metadata["kilo_execution_by_step"][step_name]["health_status"] = health_status.value
    state.metadata["kilo_execution_by_step"][step_name]["retry_attempts"] = retry_attempts
    record_supervisor_event(
        state,
        event_type="KILO_EXECUTION_RECORDED",
        status=health_status,
        metadata={
            "watchdog_id": watchdog.watchdog_id,
            "execution_id": execution_id,
            "step_name": step_name,
            "retry_attempts": retry_attempts,
        },
    )
    if retry_attempts > 0:
        record_supervisor_event(
            state,
            event_type="RETRY_TRIGGERED",
            status=ExecutionHealthStatus.RECOVERING,
            metadata={
                "execution_id": execution_id,
                "step_name": step_name,
                "retry_attempts": retry_attempts,
            },
        )
    return watchdog.watchdog_id


def annotate_kilo_execution_result(
    state: RuntimeState,
    *,
    step_name: str,
    result_metadata: dict[str, Any],
    retry_attempts: int,
    health_status: ExecutionHealthStatus,
) -> None:
    queue_item_id = _current_queue_item_id(state)
    if queue_item_id:
        _sync_queue_item_health(
            state,
            queue_item_id=queue_item_id,
            health_status=health_status,
            watchdog_id=result_metadata.get("watchdog_id"),
            last_heartbeat_at=datetime.now(UTC),
            retry_attempts=retry_attempts,
        )
    session_id = _current_session_id(state)
    if session_id:
        session = SessionRegistry.default().get_session(session_id)
        if session is not None:
            SessionRegistry.default().save_session(
                session.model_copy(
                    update={
                        "health_status": health_status.value,
                        "retry_attempts": retry_attempts,
                        "metadata": {
                            **session.metadata,
                            "health_status": health_status.value,
                            "retry_attempts": retry_attempts,
                        },
                    }
                )
            )
            state.metadata.setdefault("sessions", {})[session_id] = (
                SessionRegistry.default().get_session(session_id).model_dump(mode="json")
            )
    state.metadata["health_status"] = health_status.value
    state.metadata["retry_attempts"] = retry_attempts
    state.metadata["kilo_execution_by_step"][step_name]["health_status"] = health_status.value
    state.metadata["kilo_execution_by_step"][step_name]["retry_attempts"] = retry_attempts
    state.metadata["kilo_execution_by_step"][step_name]["watchdog_id"] = result_metadata.get("watchdog_id")
    state.metadata["kilo_execution_by_step"][step_name]["last_heartbeat_at"] = datetime.now(UTC).isoformat()
    SupervisorRegistry.default()._sync_runtime_metadata(state)


def detect_stuck_watchdogs(state: RuntimeState) -> None:
    previous_dead_letter_count = int(state.metadata.get("dead_letter_count", 0))
    SupervisorRegistry.default().detect_stuck(runtime_state=state)
    action_id = state.metadata.get("recovery_action_id")
    if action_id:
        action = next(
            (
                item
                for item in SupervisorRegistry.default().list_recovery_actions()
                if item.action_id == action_id
            ),
            None,
        )
        if action is not None:
            propose_execution_decision(
                state,
                context=build_execution_context(
                    state,
                    task_id=str(action.metadata.get("task_id")) if action.metadata.get("task_id") else None,
                    retry_count=int(action.metadata.get("retry_attempts", 0)),
                    max_retries=int(action.metadata.get("max_retries", 1)),
                    stuck_detected=True,
                    dead_lettered=int(state.metadata.get("dead_letter_count", 0)) > previous_dead_letter_count,
                    real_code_touched=False,
                    metadata={
                        "source": "supervisor_stuck_detection",
                        "recovery_action_id": action.action_id,
                        "recovery_action_type": action.action_type.value,
                    },
                ),
            )
            propose_adaptive_plan(
                state,
                context=build_adaptive_planning_context(
                    state,
                    trigger_reason=(
                        "dead_letter_risk"
                        if action.action_type.value == "MARK_DEAD_LETTER"
                        else "supervisor_stuck"
                    ),
                    source_task_id=str(action.metadata.get("task_id")) if action.metadata.get("task_id") else None,
                    retry_count=int(action.metadata.get("retry_attempts", 0)),
                    max_retries=int(action.metadata.get("max_retries", 1)),
                    dead_letter_risk=(
                        action.action_type.value == "MARK_DEAD_LETTER"
                        or int(state.metadata.get("dead_letter_count", 0)) > previous_dead_letter_count
                    ),
                    metadata={
                        "source": "supervisor_stuck_detection",
                        "recovery_action_id": action.action_id,
                        "recovery_action_type": action.action_type.value,
                    },
                ),
            )
    sync_timeline_for_state(state)


def _sync_queue_item_health(
    state: RuntimeState,
    *,
    queue_item_id: str,
    health_status: ExecutionHealthStatus,
    watchdog_id: str | None,
    last_heartbeat_at: datetime,
    retry_attempts: int = 0,
) -> None:
    queue_id = str(state.metadata.get("queue_id", "")).strip()
    if not queue_id:
        return
    queue = TaskQueueRegistry.default().get_queue(queue_id)
    if queue is None:
        return
    for item in queue.items:
        if item.queue_item_id != queue_item_id:
            continue
        TaskQueueRegistry.default().update_item_status(
            queue_id,
            queue_item_id,
            item.status,
            metadata={
                **item.metadata,
                "health_status": health_status.value,
                "watchdog_id": watchdog_id,
                "recovery_action_id": item.metadata.get("recovery_action_id"),
                "dead_letter_id": item.metadata.get("dead_letter_id"),
                "retry_attempts": retry_attempts,
                "last_heartbeat_at": last_heartbeat_at.isoformat(),
            },
        )
        refreshed = TaskQueueRegistry.default().get_queue(queue_id)
        if refreshed is not None:
            state.metadata["task_queue"] = refreshed.model_dump(mode="json")
        return


def _find_watchdog(workflow_run_id: str, target_type: str, target_id: str):
    for watchdog in SupervisorRegistry.default().list_watchdogs():
        if (
            watchdog.workflow_run_id == workflow_run_id
            and watchdog.target_type == target_type
            and watchdog.target_id == target_id
        ):
            return watchdog
    return None


def _current_session_id(state: RuntimeState) -> str | None:
    value = state.metadata.get("current_session_id")
    return str(value) if value else None


def _current_queue_item_id(state: RuntimeState) -> str | None:
    value = state.metadata.get("current_queue_item_id")
    return str(value) if value else None
