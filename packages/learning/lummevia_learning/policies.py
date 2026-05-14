from __future__ import annotations

from lummevia_learning.schemas import LearningSeverity


REPEATED_QA_FAILURE_THRESHOLD = 2
HIGH_RETRY_THRESHOLD = 2
HIGH_COST_THRESHOLD = 3.0
HIGH_LATENCY_THRESHOLD_MS = 1200
MANY_NEEDS_REVIEW_THRESHOLD = 2
LOW_PROMPT_SCORE_THRESHOLD = 0.7
FREQUENT_RECOVERY_MIN_COUNT = 2
FREQUENT_RECOVERY_RATIO = 0.4

_SEVERITY_ORDER = {
    LearningSeverity.LOW: 0,
    LearningSeverity.MEDIUM: 1,
    LearningSeverity.HIGH: 2,
    LearningSeverity.CRITICAL: 3,
}


def highest_severity(
    *severities: LearningSeverity | None,
) -> LearningSeverity | None:
    resolved = [severity for severity in severities if severity is not None]
    if not resolved:
        return None
    return max(resolved, key=lambda item: _SEVERITY_ORDER[item])
