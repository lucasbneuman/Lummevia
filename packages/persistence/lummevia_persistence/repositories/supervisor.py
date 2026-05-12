from __future__ import annotations

from lummevia_supervisor import DeadLetterItem, ExecutionWatchdog, RecoveryAction, SupervisorEvent

from lummevia_persistence.repositories.base import SnapshotRepository


class SupervisorSnapshotRepository(SnapshotRepository):
    watchdog_entity_type = "watchdog"
    recovery_action_entity_type = "recovery_action"
    event_entity_type = "supervisor_event"
    dead_letter_entity_type = "dead_letter"

    def save_watchdog(self, watchdog: ExecutionWatchdog):
        return self.save_snapshot(
            entity_type=self.watchdog_entity_type,
            entity_id=watchdog.watchdog_id,
            payload=watchdog.model_dump(mode="json"),
            metadata={"workflow_run_id": watchdog.workflow_run_id, "target_id": watchdog.target_id},
        )

    def save_recovery_action(self, action: RecoveryAction):
        return self.save_snapshot(
            entity_type=self.recovery_action_entity_type,
            entity_id=action.action_id,
            payload=action.model_dump(mode="json"),
            metadata={"workflow_run_id": action.workflow_run_id, "target_id": action.target_id},
        )

    def save_event(self, event: SupervisorEvent):
        return self.save_snapshot(
            entity_type=self.event_entity_type,
            entity_id=event.event_id,
            payload=event.model_dump(mode="json"),
            metadata={"workflow_run_id": event.workflow_run_id, "event_type": event.event_type},
        )

    def save_dead_letter(self, item: DeadLetterItem):
        return self.save_snapshot(
            entity_type=self.dead_letter_entity_type,
            entity_id=item.dead_letter_id,
            payload=item.model_dump(mode="json"),
            metadata={"workflow_run_id": item.workflow_run_id, "task_id": item.task_id},
        )

    def list_watchdogs(self) -> list[ExecutionWatchdog]:
        return [
            ExecutionWatchdog.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.watchdog_entity_type)
        ]

    def list_recovery_actions(self) -> list[RecoveryAction]:
        return [
            RecoveryAction.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.recovery_action_entity_type)
        ]

    def list_events(self) -> list[SupervisorEvent]:
        return [
            SupervisorEvent.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.event_entity_type)
        ]

    def list_dead_letters(self) -> list[DeadLetterItem]:
        return [
            DeadLetterItem.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.dead_letter_entity_type)
        ]
