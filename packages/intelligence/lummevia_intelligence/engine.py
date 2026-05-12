from __future__ import annotations

from lummevia_intelligence.policies import (
    DEFAULT_HIGH_FILES_CHANGED_COUNT,
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    should_require_human_review,
)
from lummevia_intelligence.schemas import (
    DecisionStatus,
    DecisionType,
    ExecutionContext,
    ExecutionDecision,
)


def evaluate_execution(context: ExecutionContext) -> ExecutionDecision:
    decision_type, reason, recommended_action, confidence = _resolve_decision(context)
    requires_review = should_require_human_review(
        autonomy_level=context.autonomy_level,
        decision_type=decision_type,
        confidence=confidence,
        real_code_touched=context.real_code_touched,
    )
    return ExecutionDecision(
        workflow_run_id=context.workflow_run_id,
        session_id=context.session_id,
        task_id=context.task_id,
        decision_type=decision_type,
        status=DecisionStatus.PROPOSED,
        confidence=confidence,
        reason=reason,
        recommended_action=recommended_action,
        requires_human_review=requires_review,
        metadata={
            "autonomy_level": context.autonomy_level.value,
            "retry_count": context.retry_count,
            "max_retries": context.max_retries,
            "files_changed_count": context.files_changed_count,
            "validation_status": context.validation_status,
            "qa_status": context.qa_status,
            "missing_context": context.missing_context,
            "task_too_large": context.task_too_large,
            "kilo_failed": context.kilo_failed,
            "stuck_detected": context.stuck_detected,
            "dead_lettered": context.dead_lettered,
            "real_code_touched": context.real_code_touched,
            **context.metadata,
        },
    )


def _resolve_decision(
    context: ExecutionContext,
) -> tuple[DecisionType, str, str, float]:
    confidence = context.confidence
    if context.missing_context:
        return (
            DecisionType.REQUEST_MORE_CONTEXT,
            "Missing execution context blocks a safe next step.",
            "REQUEST_CONTEXT",
            confidence if confidence is not None else 0.95,
        )
    if context.task_too_large:
        return (
            DecisionType.SPLIT_TASK,
            "Task size exceeds the MVP heuristic threshold and should be decomposed.",
            "SPLIT_TASK",
            confidence if confidence is not None else 0.88,
        )
    if context.dead_lettered or context.retry_count >= context.max_retries:
        recommended_action = "MARK_DEAD_LETTER" if context.dead_lettered else "CANCEL"
        reason = (
            "Retry budget is exhausted for this execution context."
            if not context.dead_lettered
            else "Execution reached dead-letter handling after exhausting retries."
        )
        return (
            DecisionType.STOP,
            reason,
            recommended_action,
            confidence if confidence is not None else 0.97,
        )
    if context.stuck_detected:
        return (
            DecisionType.REQUEUE,
            "Supervisor detected a stuck execution before exhausting retries.",
            "REQUEUE",
            confidence if confidence is not None else 0.82,
        )
    if context.qa_status == "FAILED":
        if context.retry_count > 0:
            return (
                DecisionType.ESCALATE_REVIEW,
                "QA failed again after a retry and should be reviewed by a human.",
                "REQUEST_REVIEW",
                confidence if confidence is not None else 0.84,
            )
        return (
            DecisionType.RETRY,
            "QA failed and the retry budget still allows another implementation pass.",
            "RETRY",
            confidence if confidence is not None else 0.78,
        )
    if context.validation_status == "FAILED":
        return (
            DecisionType.RETRY,
            "Code change validation failed and should be retried before escalation.",
            "RETRY",
            confidence if confidence is not None else 0.74,
        )
    if context.kilo_failed:
        return (
            DecisionType.RETRY,
            "Kilo execution failed before exhausting retries.",
            "RETRY",
            confidence if confidence is not None else 0.72,
        )
    if context.files_changed_count >= DEFAULT_HIGH_FILES_CHANGED_COUNT:
        return (
            DecisionType.ESCALATE_REVIEW,
            "The change set is large enough to require explicit human review.",
            "REQUEST_REVIEW",
            confidence if confidence is not None else 0.86,
        )
    if confidence is not None and confidence < DEFAULT_LOW_CONFIDENCE_THRESHOLD:
        return (
            DecisionType.ESCALATE_REVIEW,
            "Decision confidence is below the safe threshold.",
            "REQUEST_REVIEW",
            confidence,
        )
    return (
        DecisionType.CONTINUE,
        "No blocking heuristic was triggered for this execution context.",
        "CONTINUE",
        confidence if confidence is not None else 0.7,
    )
