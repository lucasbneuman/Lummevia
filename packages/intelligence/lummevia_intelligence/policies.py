from __future__ import annotations

from lummevia_intelligence.schemas import AutonomyLevel, DecisionType


DEFAULT_AUTONOMY_LEVEL = AutonomyLevel.MANUAL
DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.5
DEFAULT_HIGH_FILES_CHANGED_COUNT = 8


def can_apply_decision(
    *,
    autonomy_level: AutonomyLevel,
    decision_type: DecisionType,
    real_code_touched: bool,
) -> bool:
    if autonomy_level == AutonomyLevel.MANUAL:
        return False
    if autonomy_level == AutonomyLevel.ASSISTED:
        return decision_type == DecisionType.CONTINUE
    if autonomy_level == AutonomyLevel.SUPERVISED:
        return (
            decision_type in {DecisionType.CONTINUE, DecisionType.RETRY, DecisionType.REQUEUE}
            and not real_code_touched
        )
    return (
        decision_type
        in {
            DecisionType.CONTINUE,
            DecisionType.RETRY,
            DecisionType.REQUEUE,
            DecisionType.REQUEST_MORE_CONTEXT,
        }
        and not real_code_touched
    )


def should_require_human_review(
    *,
    autonomy_level: AutonomyLevel,
    decision_type: DecisionType,
    confidence: float,
    real_code_touched: bool,
) -> bool:
    if decision_type in {
        DecisionType.ESCALATE_REVIEW,
        DecisionType.SPLIT_TASK,
        DecisionType.STOP,
        DecisionType.DISCARD_CHANGES,
    }:
        return True
    if confidence < DEFAULT_LOW_CONFIDENCE_THRESHOLD:
        return True
    if autonomy_level == AutonomyLevel.MANUAL and decision_type != DecisionType.CONTINUE:
        return True
    if autonomy_level == AutonomyLevel.ASSISTED and decision_type in {
        DecisionType.RETRY,
        DecisionType.REQUEUE,
        DecisionType.SPLIT_TASK,
        DecisionType.STOP,
    }:
        return True
    if autonomy_level == AutonomyLevel.SUPERVISED and real_code_touched and decision_type in {
        DecisionType.RETRY,
        DecisionType.REQUEUE,
    }:
        return True
    return False
