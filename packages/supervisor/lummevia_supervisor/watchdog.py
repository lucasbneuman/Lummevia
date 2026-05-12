from __future__ import annotations

from datetime import UTC, datetime

from lummevia_supervisor.policies import is_watchdog_stale
from lummevia_supervisor.schemas import ExecutionWatchdog, WatchdogStatus


def heartbeat_watchdog(
    watchdog: ExecutionWatchdog,
    *,
    heartbeat_at: datetime | None = None,
) -> ExecutionWatchdog:
    return watchdog.model_copy(
        update={
            "last_heartbeat_at": heartbeat_at or datetime.now(UTC),
            "status": WatchdogStatus.ACTIVE,
        }
    )


def mark_watchdog_stuck(
    watchdog: ExecutionWatchdog,
    *,
    now: datetime | None = None,
) -> ExecutionWatchdog:
    detected_at = now or datetime.now(UTC)
    return watchdog.model_copy(
        update={
            "status": WatchdogStatus.STUCK,
            "metadata": {
                **watchdog.metadata,
                "stuck_detected": True,
                "stuck_detected_at": detected_at.isoformat(),
            },
        }
    )


def watchdog_is_stuck(
    watchdog: ExecutionWatchdog,
    *,
    now: datetime | None = None,
) -> bool:
    if watchdog.status != WatchdogStatus.ACTIVE:
        return False
    reference = now or datetime.now(UTC)
    return is_watchdog_stale(
        last_heartbeat_at=watchdog.last_heartbeat_at,
        timeout_seconds=watchdog.timeout_seconds,
        now=reference,
    )
