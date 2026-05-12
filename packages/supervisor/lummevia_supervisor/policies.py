from __future__ import annotations

from datetime import datetime, timedelta

from lummevia_supervisor.schemas import ExecutionHealthStatus, RecoveryActionType


DEFAULT_WATCHDOG_TIMEOUT_SECONDS = 300
DEFAULT_MAX_RECOVERY_ATTEMPTS = 1


def is_watchdog_stale(
    *,
    last_heartbeat_at: datetime,
    timeout_seconds: int,
    now: datetime,
) -> bool:
    return now - last_heartbeat_at > timedelta(seconds=timeout_seconds)


def resolve_recovery_action_type(
    *,
    retry_attempts: int,
    max_retries: int,
) -> RecoveryActionType:
    if retry_attempts >= max_retries:
        return RecoveryActionType.MARK_DEAD_LETTER
    return RecoveryActionType.RETRY


def resolve_recovery_health_status(action_type: RecoveryActionType) -> ExecutionHealthStatus:
    if action_type == RecoveryActionType.MARK_DEAD_LETTER:
        return ExecutionHealthStatus.DEAD_LETTER
    return ExecutionHealthStatus.RECOVERING
