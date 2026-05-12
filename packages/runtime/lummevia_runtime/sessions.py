from __future__ import annotations

from typing import Any

from lummevia_core import AgentRole, TaskPackage
from lummevia_kilo import KiloExecutionMode, KiloExecutionResult
from lummevia_memory import (
    MemoryCategory,
    MemorySourceType,
    ProjectMemoryRegistry,
    build_project_memory_metadata,
)
from lummevia_sessions import SessionRegistry, SessionStatus, TaskExecutionSession

from lummevia_runtime.state import RuntimeState
from lummevia_runtime.timeline import sync_timeline_for_state


def create_task_execution_session(
    state: RuntimeState,
    *,
    task_package: TaskPackage,
    step_name: str,
    role: AgentRole,
    mode: KiloExecutionMode,
) -> TaskExecutionSession:
    registry = SessionRegistry.default()
    session = registry.create_session(
        task_id=task_package.task_id,
        project=state.run.project,
        issue_id=state.run.issue_id,
        role=role,
        mode=mode,
        metadata={
            "run_id": state.run.run_id,
            "workflow": state.run.workflow_name,
            "step_name": step_name,
        },
    )
    session = registry.add_event(
        session.session_id,
        type="SESSION_CREATED",
        message=f"Task execution session created for {task_package.task_id}.",
        metadata={
            "task_id": task_package.task_id,
            "step_name": step_name,
            "role": role.value,
            "mode": mode.value,
        },
    )
    session = registry.add_output(
        session.session_id,
        output_type="task_package",
        content=f"TaskPackage {task_package.task_id} is ready for execution tracking.",
        metadata={
            "task_id": task_package.task_id,
            "status": task_package.status,
        },
    )
    session = registry.update_status(
        session.session_id,
        status=SessionStatus.RUNNING,
        role=role,
        mode=mode,
        metadata={"current_step": step_name},
    )
    attach_session_to_task_package(
        state,
        task_id=task_package.task_id,
        session_id=session.session_id,
    )
    sync_session_to_runtime_metadata(state, session)
    return session


def attach_session_to_task_package(
    state: RuntimeState,
    *,
    task_id: str,
    session_id: str,
) -> None:
    state.metadata["current_session_id"] = session_id
    state.metadata.setdefault("task_package_sessions", {})[task_id] = session_id
    if state.artifacts.current_task_package is not None and state.artifacts.current_task_package.task_id == task_id:
        state.artifacts.current_task_package = state.artifacts.current_task_package.model_copy(
            update={
                "metadata": {
                    **state.artifacts.current_task_package.metadata,
                    "session_id": session_id,
                }
            }
        )
    state.artifacts.task_packages = [
        task_package.model_copy(
            update={
                "metadata": (
                    {
                        **task_package.metadata,
                        "session_id": session_id,
                    }
                    if task_package.task_id == task_id
                    else task_package.metadata
                )
            }
        )
        for task_package in state.artifacts.task_packages
    ]


def get_current_session(state: RuntimeState) -> TaskExecutionSession | None:
    session_id = str(state.metadata.get("current_session_id", "")).strip()
    if not session_id:
        return None
    return SessionRegistry.default().get_session(session_id)


def record_kilo_execution_for_session(
    state: RuntimeState,
    *,
    step_name: str,
    role: AgentRole,
    mode: KiloExecutionMode,
    result: KiloExecutionResult,
) -> TaskExecutionSession | None:
    session = get_current_session(state)
    if session is None:
        return None
    registry = SessionRegistry.default()
    session = registry.add_event(
        session.session_id,
        type="KILO_EXECUTION",
        message=(
            f"Kilo execution {result.execution_id} finished with "
            f"{result.final_status.value}."
        ),
        metadata={
            "step_name": step_name,
            "execution_id": result.execution_id,
            "status": result.status.value,
            "final_status": result.final_status.value,
            "retry_count": result.retry_count,
            "attempts_count": len(result.attempts),
        },
    )
    session = registry.add_output(
        session.session_id,
        output_type="kilo_execution",
        content=result.summary,
        metadata={
            "execution_id": result.execution_id,
            "step_name": step_name,
            "task_id": result.task_id,
            "generated_artifacts": result.generated_artifacts,
            "logs": result.logs,
        },
    )
    session = registry.update_status(
        session.session_id,
        status=SessionStatus.RUNNING,
        role=role,
        mode=mode,
        attempts=session.attempts + len(result.attempts),
        metadata={
            "current_step": step_name,
            "last_execution_id": result.execution_id,
        },
    )
    sync_session_to_runtime_metadata(state, session)
    return session


def add_session_output(
    state: RuntimeState,
    *,
    output_type: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> TaskExecutionSession | None:
    session = get_current_session(state)
    if session is None:
        return None
    session = SessionRegistry.default().add_output(
        session.session_id,
        output_type=output_type,
        content=content,
        metadata=metadata or {},
    )
    sync_session_to_runtime_metadata(state, session)
    return session


def update_task_execution_session(
    state: RuntimeState,
    *,
    status: SessionStatus,
    role: AgentRole,
    mode: KiloExecutionMode,
    metadata: dict[str, Any] | None = None,
) -> TaskExecutionSession | None:
    session = get_current_session(state)
    if session is None:
        return None
    session = SessionRegistry.default().update_status(
        session.session_id,
        status=status,
        role=role,
        mode=mode,
        attempts=session.attempts,
        metadata=metadata or {},
    )
    sync_session_to_runtime_metadata(state, session)
    if status == SessionStatus.COMPLETED:
        memory_record = ProjectMemoryRegistry.default().add_memory(
            project=state.run.project,
            category=MemoryCategory.TASK_LEARNING,
            title=f"Task learning for {session.task_id}",
            content=(
                f"Task session {session.session_id} completed for {session.task_id}. "
                f"Outputs: {len(session.outputs)}. Events: {len(session.events)}. "
                f"Final metadata: {session.metadata}."
            ),
            source_type=MemorySourceType.SESSION,
            source_id=session.session_id,
            tags=["task", "learning", session.task_id, state.run.issue_id],
            metadata={
                "run_id": state.run.run_id,
                "issue_id": state.run.issue_id,
                "task_id": session.task_id,
                "session_status": session.status.value,
            },
        )
        memory_metadata = build_project_memory_metadata(
            state.run.project,
            created_records=[memory_record],
        )
        state.metadata.setdefault("memory_record_ids", []).append(memory_record.memory_id)
        state.metadata.update(memory_metadata)
        state.metadata["memory_records_created"] = len(state.metadata["memory_record_ids"])
    return session


def sync_session_to_runtime_metadata(
    state: RuntimeState,
    session: TaskExecutionSession,
) -> None:
    state.metadata.setdefault("sessions", {})[session.session_id] = session.model_dump(mode="json")
    state.metadata["current_session_id"] = session.session_id
    state.metadata["session_status"] = session.status.value
    state.metadata["session_role"] = session.role.value
    state.metadata["session_attempts"] = session.attempts
    state.metadata["output_count"] = len(session.outputs)
    state.metadata["event_count"] = len(session.events)
    sync_timeline_for_state(state)
