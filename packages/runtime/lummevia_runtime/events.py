from __future__ import annotations

from enum import Enum
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from lummevia_core import AgentRole, WorkflowRunEvent, WorkflowRunStatus

from lummevia_runtime.state import RuntimeState
from lummevia_runtime.timeline import sync_timeline_for_state


class RuntimeEventType(str, Enum):
    STEP_STARTED = "STEP_STARTED"
    STEP_COMPLETED = "STEP_COMPLETED"
    STEP_FAILED = "STEP_FAILED"
    LOOP_REENTERED = "LOOP_REENTERED"


def append_runtime_event(
    state: RuntimeState,
    *,
    event_type: RuntimeEventType,
    step_name: str,
    status: WorkflowRunStatus,
    message: str,
    role: AgentRole,
    metadata: dict[str, Any] | None = None,
) -> RuntimeState:
    state.run.events.append(
        WorkflowRunEvent(
            event_id=f"evt-{uuid4()}",
            step_name=step_name,
            status=status,
            message=message,
            metadata={
                "type": event_type.value,
                "role": role.value,
                "loop_count": state.loop_count,
                **(metadata or {}),
            },
        )
    )
    sync_timeline_for_state(state)
    return state


def start_step(state: RuntimeState, *, step_name: str, role: AgentRole) -> RuntimeState:
    from lummevia_runtime.strategy import resolve_execution_strategy_for_step

    resolve_execution_strategy_for_step(
        state,
        role=role.value,
        step_name=step_name,
    )
    state.run.status = WorkflowRunStatus.RUNNING
    state.run.current_step = step_name
    state.current_role = role
    return append_runtime_event(
        state,
        event_type=RuntimeEventType.STEP_STARTED,
        step_name=step_name,
        status=WorkflowRunStatus.RUNNING,
        message=f"Step '{step_name}' started for role '{role.value}'.",
        role=role,
    )


def complete_step(
    state: RuntimeState,
    *,
    step_name: str,
    role: AgentRole,
    metadata: dict[str, Any] | None = None,
) -> RuntimeState:
    return append_runtime_event(
        state,
        event_type=RuntimeEventType.STEP_COMPLETED,
        step_name=step_name,
        status=WorkflowRunStatus.COMPLETED,
        message=f"Step '{step_name}' completed for role '{role.value}'.",
        role=role,
        metadata=metadata,
    )


def fail_step(
    state: RuntimeState,
    *,
    step_name: str,
    role: AgentRole,
    error: Exception,
) -> RuntimeState:
    state.run.status = WorkflowRunStatus.FAILED
    return append_runtime_event(
        state,
        event_type=RuntimeEventType.STEP_FAILED,
        step_name=step_name,
        status=WorkflowRunStatus.FAILED,
        message=f"Step '{step_name}' failed for role '{role.value}': {error}",
        role=role,
        metadata={"error": str(error)},
    )


def log_loop_reentered(state: RuntimeState, *, step_name: str, role: AgentRole) -> RuntimeState:
    return append_runtime_event(
        state,
        event_type=RuntimeEventType.LOOP_REENTERED,
        step_name=step_name,
        status=WorkflowRunStatus.RUNNING,
        message="DEV-QA loop reentered for implementation rework.",
        role=role,
    )


def record_lifecycle_event(
    state: RuntimeState,
    *,
    event_type: str,
    title: str,
    description: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    state.metadata.setdefault("lifecycle_events", []).append(
        {
            "event_id": f"lifecycle-event-{uuid4()}",
            "workflow_run_id": state.run.run_id,
            "event_type": event_type,
            "title": title,
            "description": description,
            "created_at": (
                state.run.events[-1].created_at.isoformat()
                if state.run.events
                else datetime.now(UTC).isoformat()
            ),
            "metadata": metadata or {},
        }
    )
