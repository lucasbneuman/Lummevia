from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from lummevia_capabilities import CapabilityAllocator
from lummevia_queue import TaskQueueRegistry, TaskQueueStatus
from lummevia_resources import ResourceRegistry, WorkspaceAllocator
from lummevia_sessions import SessionRegistry, SessionStatus

from lummevia_supervisor.policies import (
    DEFAULT_MAX_RECOVERY_ATTEMPTS,
    DEFAULT_WATCHDOG_TIMEOUT_SECONDS,
    resolve_recovery_action_type,
    resolve_recovery_health_status,
)
from lummevia_supervisor.recovery import complete_recovery_action
from lummevia_supervisor.schemas import (
    DeadLetterItem,
    ExecutionHealthStatus,
    ExecutionWatchdog,
    RecoveryAction,
    RecoveryActionStatus,
    RecoveryActionType,
    SupervisorEvent,
    WatchdogStatus,
)
from lummevia_supervisor.watchdog import heartbeat_watchdog, mark_watchdog_stuck, watchdog_is_stuck


class SupervisorRegistry:
    _default_instance: ClassVar["SupervisorRegistry" | None] = None

    def __init__(self) -> None:
        self._events: dict[str, SupervisorEvent] = {}
        self._watchdogs: dict[str, ExecutionWatchdog] = {}
        self._recovery_actions: dict[str, RecoveryAction] = {}
        self._dead_letters: dict[str, DeadLetterItem] = {}

    @classmethod
    def default(cls) -> "SupervisorRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._events.clear()
        self._watchdogs.clear()
        self._recovery_actions.clear()
        self._dead_letters.clear()

    def register_watchdog(
        self,
        *,
        workflow_run_id: str,
        target_type: str,
        target_id: str,
        timeout_seconds: int = DEFAULT_WATCHDOG_TIMEOUT_SECONDS,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionWatchdog:
        watchdog = ExecutionWatchdog(
            workflow_run_id=workflow_run_id,
            target_type=target_type,
            target_id=target_id,
            timeout_seconds=timeout_seconds,
            metadata=metadata or {},
        )
        self._watchdogs[watchdog.watchdog_id] = watchdog
        return watchdog

    def heartbeat(
        self,
        watchdog_id: str,
        *,
        heartbeat_at: datetime | None = None,
    ) -> ExecutionWatchdog:
        watchdog = self._watchdogs[watchdog_id]
        updated = heartbeat_watchdog(watchdog, heartbeat_at=heartbeat_at)
        self._watchdogs[watchdog_id] = updated
        return updated

    def detect_stuck(
        self,
        *,
        runtime_state=None,
        now: datetime | None = None,
    ) -> list[ExecutionWatchdog]:
        reference = now or datetime.now(UTC)
        detected: list[ExecutionWatchdog] = []
        for watchdog in self.list_watchdogs():
            if not watchdog_is_stuck(watchdog, now=reference):
                continue
            stuck = mark_watchdog_stuck(watchdog, now=reference)
            self._watchdogs[watchdog.watchdog_id] = stuck
            detected.append(stuck)
            self.create_supervisor_event(
                workflow_run_id=stuck.workflow_run_id,
                session_id=str(stuck.metadata.get("session_id")) if stuck.metadata.get("session_id") else None,
                queue_item_id=(
                    str(stuck.metadata.get("queue_item_id")) if stuck.metadata.get("queue_item_id") else None
                ),
                event_type="EXECUTION_STUCK",
                status=ExecutionHealthStatus.STUCK,
                metadata={
                    "watchdog_id": stuck.watchdog_id,
                    "target_type": stuck.target_type,
                    "target_id": stuck.target_id,
                    **stuck.metadata,
                },
            )
            self._apply_stuck_recovery(stuck, runtime_state=runtime_state)
        if runtime_state is not None:
            self._sync_runtime_metadata(runtime_state)
        return detected

    def create_supervisor_event(
        self,
        *,
        workflow_run_id: str,
        event_type: str,
        status: ExecutionHealthStatus,
        session_id: str | None = None,
        queue_item_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SupervisorEvent:
        event = SupervisorEvent(
            workflow_run_id=workflow_run_id,
            session_id=session_id,
            queue_item_id=queue_item_id,
            event_type=event_type,
            status=status,
            metadata=metadata or {},
        )
        self._events[event.event_id] = event
        return event

    def create_recovery_action(
        self,
        *,
        workflow_run_id: str,
        target_type: str,
        target_id: str,
        action_type: RecoveryActionType,
        metadata: dict[str, Any] | None = None,
    ) -> RecoveryAction:
        action = RecoveryAction(
            workflow_run_id=workflow_run_id,
            target_type=target_type,
            target_id=target_id,
            action_type=action_type,
            metadata=metadata or {},
        )
        self._recovery_actions[action.action_id] = action
        return action

    def mark_dead_letter(
        self,
        *,
        workflow_run_id: str,
        task_id: str,
        queue_item_id: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> DeadLetterItem:
        item = DeadLetterItem(
            workflow_run_id=workflow_run_id,
            task_id=task_id,
            queue_item_id=queue_item_id,
            reason=reason,
            metadata=metadata or {},
        )
        self._dead_letters[item.dead_letter_id] = item
        return item

    def cancel_workflow(self, state) -> Any:
        workflow_run_id = state.run.run_id
        queue_id = str(state.metadata.get("queue_id", "")).strip()
        current_queue_item_id = str(state.metadata.get("current_queue_item_id", "")).strip()
        session_id = str(state.metadata.get("current_session_id", "")).strip()

        workspace_id = str(state.metadata.get("workspace_id", "")).strip()
        if workspace_id:
            workspace = ResourceRegistry.default().get_workspace(workspace_id)
            if workspace is not None and workspace.status.value != "RELEASED":
                released_workspace = WorkspaceAllocator().release_workspace(
                    workspace_id,
                    metadata={
                        "cancelled": True,
                        "workflow_run_id": workflow_run_id,
                    },
                )
                state.metadata["workspace_status"] = "RELEASED"
                state.metadata["current_workspace"] = released_workspace.model_dump(mode="json")
                state.metadata.setdefault("workspace_allocations", {})[workspace_id] = (
                    released_workspace.model_dump(mode="json")
                )

        allocation_id = str(state.metadata.get("allocation_id", "")).strip()
        if allocation_id:
            CapabilityAllocator.default().release_allocation(allocation_id)

        if queue_id:
            queue = TaskQueueRegistry.default().get_queue(queue_id)
            if queue is not None:
                for item in queue.items:
                    if item.status in {TaskQueueStatus.COMPLETED, TaskQueueStatus.CANCELLED}:
                        continue
                    TaskQueueRegistry.default().update_item_status(
                        queue_id,
                        item.queue_item_id,
                        TaskQueueStatus.CANCELLED,
                        metadata={
                            **item.metadata,
                            "health_status": ExecutionHealthStatus.CANCELLED.value,
                            "workflow_cancelled": True,
                        },
                    )
                refreshed_queue = TaskQueueRegistry.default().get_queue(queue_id)
                if refreshed_queue is not None:
                    state.metadata["task_queue"] = refreshed_queue.model_dump(mode="json")
                    state.metadata["queue_size"] = len(refreshed_queue.items)
                    state.metadata["ready_count"] = len(
                        [item for item in refreshed_queue.items if item.status == TaskQueueStatus.READY]
                    )
                    state.metadata["blocked_count"] = len(
                        [item for item in refreshed_queue.items if item.status == TaskQueueStatus.BLOCKED]
                    )
                    state.metadata["completed_count"] = len(
                        [item for item in refreshed_queue.items if item.status == TaskQueueStatus.COMPLETED]
                    )

        if session_id:
            session = SessionRegistry.default().get_session(session_id)
            if session is not None:
                updated = SessionRegistry.default().update_status(
                    session_id,
                    status=SessionStatus.CANCELLED,
                    attempts=session.attempts,
                    metadata={
                        **session.metadata,
                        "health_status": ExecutionHealthStatus.CANCELLED.value,
                        "workflow_cancelled": True,
                    },
                )
                state.metadata.setdefault("sessions", {})[session_id] = updated.model_dump(mode="json")

        action = self.create_recovery_action(
            workflow_run_id=workflow_run_id,
            target_type="WorkflowRun",
            target_id=workflow_run_id,
            action_type=RecoveryActionType.CANCEL,
            metadata={"queue_item_id": current_queue_item_id or None},
        )
        self._recovery_actions[action.action_id] = complete_recovery_action(action)
        self.create_supervisor_event(
            workflow_run_id=workflow_run_id,
            session_id=session_id or None,
            queue_item_id=current_queue_item_id or None,
            event_type="WORKFLOW_CANCELLED",
            status=ExecutionHealthStatus.CANCELLED,
            metadata={"recovery_action_id": action.action_id},
        )
        state.metadata["workflow_cancelled"] = True
        state.metadata["health_status"] = ExecutionHealthStatus.CANCELLED.value
        state.metadata["stuck_detected"] = False
        state.metadata["active_locks_count"] = len(ResourceRegistry.default().list_active_locks())
        state.metadata["resource_registry"] = {
            "lock_count": len(ResourceRegistry.default().list_locks()),
            "active_lock_count": len(ResourceRegistry.default().list_active_locks()),
            "workspace_count": len(ResourceRegistry.default().list_workspaces()),
        }
        self._complete_watchdogs_for_run(workflow_run_id, status=WatchdogStatus.CANCELLED)
        self._sync_runtime_metadata(state)
        return state

    def list_dead_letters(self) -> list[DeadLetterItem]:
        return sorted(self._dead_letters.values(), key=lambda item: (item.created_at, item.dead_letter_id), reverse=True)

    def list_watchdogs(self) -> list[ExecutionWatchdog]:
        return sorted(self._watchdogs.values(), key=lambda item: (item.created_at, item.watchdog_id), reverse=True)

    def list_recovery_actions(self) -> list[RecoveryAction]:
        return sorted(
            self._recovery_actions.values(),
            key=lambda item: (item.created_at, item.action_id),
            reverse=True,
        )

    def list_events(self) -> list[SupervisorEvent]:
        return sorted(self._events.values(), key=lambda item: (item.created_at, item.event_id), reverse=True)

    def _apply_stuck_recovery(self, watchdog: ExecutionWatchdog, *, runtime_state=None) -> None:
        retry_attempts = int(watchdog.metadata.get("retry_attempts", 0))
        max_retries = int(watchdog.metadata.get("max_retries", DEFAULT_MAX_RECOVERY_ATTEMPTS))
        action_type = resolve_recovery_action_type(
            retry_attempts=retry_attempts,
            max_retries=max_retries,
        )
        action = self.create_recovery_action(
            workflow_run_id=watchdog.workflow_run_id,
            target_type=watchdog.target_type,
            target_id=watchdog.target_id,
            action_type=action_type,
            metadata={
                **watchdog.metadata,
                "watchdog_id": watchdog.watchdog_id,
                "retry_attempts": retry_attempts,
                "max_retries": max_retries,
            },
        )
        next_health = resolve_recovery_health_status(action_type)
        self.create_supervisor_event(
            workflow_run_id=watchdog.workflow_run_id,
            session_id=str(watchdog.metadata.get("session_id")) if watchdog.metadata.get("session_id") else None,
            queue_item_id=(
                str(watchdog.metadata.get("queue_item_id")) if watchdog.metadata.get("queue_item_id") else None
            ),
            event_type="RECOVERY_TRIGGERED",
            status=next_health,
            metadata={
                "recovery_action_id": action.action_id,
                "action_type": action.action_type.value,
                "watchdog_id": watchdog.watchdog_id,
            },
        )
        if action_type == RecoveryActionType.RETRY:
            self.create_supervisor_event(
                workflow_run_id=watchdog.workflow_run_id,
                session_id=str(watchdog.metadata.get("session_id")) if watchdog.metadata.get("session_id") else None,
                queue_item_id=(
                    str(watchdog.metadata.get("queue_item_id")) if watchdog.metadata.get("queue_item_id") else None
                ),
                event_type="TASK_REQUEUED",
                status=ExecutionHealthStatus.RECOVERING,
                metadata={
                    "recovery_action_id": action.action_id,
                    "watchdog_id": watchdog.watchdog_id,
                },
            )
        if action_type == RecoveryActionType.MARK_DEAD_LETTER:
            task_id = str(watchdog.metadata.get("task_id", watchdog.target_id))
            queue_item_id = str(watchdog.metadata.get("queue_item_id", watchdog.target_id))
            dead_letter = self.mark_dead_letter(
                workflow_run_id=watchdog.workflow_run_id,
                task_id=task_id,
                queue_item_id=queue_item_id,
                reason="Retries exhausted after stuck detection.",
                metadata={"recovery_action_id": action.action_id},
            )
            self.create_supervisor_event(
                workflow_run_id=watchdog.workflow_run_id,
                session_id=str(watchdog.metadata.get("session_id")) if watchdog.metadata.get("session_id") else None,
                queue_item_id=queue_item_id,
                event_type="DEAD_LETTERED",
                status=ExecutionHealthStatus.DEAD_LETTER,
                metadata={
                    "dead_letter_id": dead_letter.dead_letter_id,
                    "recovery_action_id": action.action_id,
                },
            )
        if runtime_state is not None:
            self._sync_runtime_targets(
                runtime_state,
                watchdog=watchdog,
                action=action,
                next_health=next_health,
            )

    def _sync_runtime_targets(
        self,
        state,
        *,
        watchdog: ExecutionWatchdog,
        action: RecoveryAction,
        next_health: ExecutionHealthStatus,
    ) -> None:
        state.metadata["stuck_detected"] = True
        state.metadata["health_status"] = next_health.value
        state.metadata["watchdog_id"] = watchdog.watchdog_id
        state.metadata["recovery_action_id"] = action.action_id
        state.metadata["retry_attempts"] = int(action.metadata.get("retry_attempts", 0))
        if watchdog.target_type == "TaskQueueItem":
            self._sync_queue_item_supervisor_metadata(
                queue_item_id=watchdog.target_id,
                health_status=next_health,
                recovery_action_id=action.action_id,
                retry_attempts=int(action.metadata.get("retry_attempts", 0)),
            )
            queue_id = str(state.metadata.get("queue_id", "")).strip()
            if queue_id:
                queue = TaskQueueRegistry.default().get_queue(queue_id)
                if queue is not None:
                    state.metadata["task_queue"] = queue.model_dump(mode="json")
        if watchdog.target_type == "TaskExecutionSession":
            self._sync_session_supervisor_metadata(
                session_id=watchdog.target_id,
                health_status=next_health,
                watchdog_id=watchdog.watchdog_id,
                retry_attempts=int(action.metadata.get("retry_attempts", 0)),
                recovery_action_id=action.action_id,
            )
            session = SessionRegistry.default().get_session(watchdog.target_id)
            if session is not None:
                state.metadata.setdefault("sessions", {})[watchdog.target_id] = session.model_dump(mode="json")
        kilo_by_step = state.metadata.get("kilo_execution_by_step", {})
        if isinstance(kilo_by_step, dict):
            for step_payload in kilo_by_step.values():
                if not isinstance(step_payload, dict):
                    continue
                if step_payload.get("watchdog_id") == watchdog.watchdog_id:
                    step_payload["health_status"] = next_health.value
                    step_payload["recovery_action_id"] = action.action_id
                    step_payload["retry_attempts"] = int(action.metadata.get("retry_attempts", 0))
                    if next_health == ExecutionHealthStatus.DEAD_LETTER:
                        step_payload["dead_letter_id"] = self._latest_dead_letter_id(watchdog.workflow_run_id)
        self._sync_runtime_metadata(state)

    def _sync_queue_item_supervisor_metadata(
        self,
        *,
        queue_item_id: str,
        health_status: ExecutionHealthStatus,
        recovery_action_id: str | None,
        retry_attempts: int,
        watchdog_id: str | None = None,
        dead_letter_id: str | None = None,
    ) -> None:
        for queue in TaskQueueRegistry.default().list_queues():
            for item in queue.items:
                if item.queue_item_id != queue_item_id:
                    continue
                next_status = item.status
                if health_status == ExecutionHealthStatus.DEAD_LETTER:
                    next_status = TaskQueueStatus.FAILED
                TaskQueueRegistry.default().update_item_status(
                    queue.queue_id,
                    queue_item_id,
                    next_status,
                    metadata={
                        **item.metadata,
                        "health_status": health_status.value,
                        "recovery_action_id": recovery_action_id,
                        "retry_attempts": retry_attempts,
                        "watchdog_id": watchdog_id or item.metadata.get("watchdog_id"),
                        "dead_letter_id": dead_letter_id,
                        "last_heartbeat_at": datetime.now(UTC).isoformat(),
                        "stuck_detected": health_status in {
                            ExecutionHealthStatus.STUCK,
                            ExecutionHealthStatus.RECOVERING,
                            ExecutionHealthStatus.DEAD_LETTER,
                        },
                    },
                )
                return

    def _sync_session_supervisor_metadata(
        self,
        *,
        session_id: str,
        health_status: ExecutionHealthStatus,
        watchdog_id: str | None,
        retry_attempts: int,
        recovery_action_id: str | None,
    ) -> None:
        session = SessionRegistry.default().get_session(session_id)
        if session is None:
            return
        updated = session.model_copy(
            update={
                "health_status": health_status.value,
                "watchdog_id": watchdog_id or session.watchdog_id,
                "retry_attempts": retry_attempts,
                "recovery_history": [
                    *session.recovery_history,
                    recovery_action_id,
                ]
                if recovery_action_id and recovery_action_id not in session.recovery_history
                else session.recovery_history,
                "metadata": {
                    **session.metadata,
                    "health_status": health_status.value,
                    "recovery_action_id": recovery_action_id,
                    "retry_attempts": retry_attempts,
                },
            }
        )
        SessionRegistry.default()._sessions[session_id] = updated

    def _complete_watchdogs_for_run(self, workflow_run_id: str, *, status: WatchdogStatus) -> None:
        for watchdog in self.list_watchdogs():
            if watchdog.workflow_run_id != workflow_run_id:
                continue
            self._watchdogs[watchdog.watchdog_id] = watchdog.model_copy(update={"status": status})

    def _latest_dead_letter_id(self, workflow_run_id: str) -> str | None:
        for item in self.list_dead_letters():
            if item.workflow_run_id == workflow_run_id:
                return item.dead_letter_id
        return None

    def _sync_runtime_metadata(self, state) -> None:
        workflow_run_id = state.run.run_id
        run_events = [
            event.model_dump(mode="json")
            for event in self.list_events()
            if event.workflow_run_id == workflow_run_id
        ]
        run_watchdogs = [
            watchdog.model_dump(mode="json")
            for watchdog in self.list_watchdogs()
            if watchdog.workflow_run_id == workflow_run_id
        ]
        run_actions = [
            action.model_dump(mode="json")
            for action in self.list_recovery_actions()
            if action.workflow_run_id == workflow_run_id
        ]
        run_dead_letters = [
            item.model_dump(mode="json")
            for item in self.list_dead_letters()
            if item.workflow_run_id == workflow_run_id
        ]
        latest_watchdog = run_watchdogs[0] if run_watchdogs else None
        latest_action = run_actions[0] if run_actions else None
        latest_dead_letter = run_dead_letters[0] if run_dead_letters else None
        state.metadata["supervisor"] = {
            "watchdogs": run_watchdogs,
            "recovery_actions": run_actions,
            "dead_letters": run_dead_letters,
            "events": run_events,
        }
        state.metadata["supervisor_events"] = run_events
        state.metadata["supervisor_event_count"] = len(run_events)
        state.metadata["watchdog_count"] = len(run_watchdogs)
        state.metadata["recovery_action_count"] = len(run_actions)
        state.metadata["dead_letter_count"] = len(run_dead_letters)
        if latest_watchdog is not None:
            state.metadata["watchdog_id"] = latest_watchdog["watchdog_id"]
            state.metadata["last_heartbeat_at"] = latest_watchdog["last_heartbeat_at"]
        if latest_action is not None:
            state.metadata["recovery_action_id"] = latest_action["action_id"]
        if latest_dead_letter is not None:
            state.metadata["dead_letter_id"] = latest_dead_letter["dead_letter_id"]
