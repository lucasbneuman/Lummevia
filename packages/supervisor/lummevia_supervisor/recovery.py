from __future__ import annotations

from datetime import UTC, datetime

from lummevia_supervisor.schemas import RecoveryAction, RecoveryActionStatus


def complete_recovery_action(action: RecoveryAction) -> RecoveryAction:
    return action.model_copy(
        update={
            "status": RecoveryActionStatus.COMPLETED,
            "completed_at": datetime.now(UTC),
        }
    )
