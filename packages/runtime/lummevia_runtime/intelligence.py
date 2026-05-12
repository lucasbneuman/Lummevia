from __future__ import annotations

from typing import Any

from lummevia_intelligence import (
    AutonomyLevel,
    DEFAULT_AUTONOMY_LEVEL,
    DecisionRegistry,
    ExecutionContext,
    ExecutionDecision,
    evaluate_execution,
)
from lummevia_reviews import HumanReviewRegistry, ReviewType

from lummevia_runtime.state import RuntimeState
from lummevia_runtime.timeline import sync_timeline_for_state


def initialize_intelligence_runtime_state(state: RuntimeState) -> None:
    state.metadata.setdefault("autonomy_level", DEFAULT_AUTONOMY_LEVEL.value)
    _sync_runtime_decisions(state)


def propose_execution_decision(
    state: RuntimeState,
    *,
    context: ExecutionContext,
) -> ExecutionDecision:
    registry = DecisionRegistry.default()
    decision = registry.create_decision(evaluate_execution(context))
    decision = _ensure_review_for_decision(state, decision)
    decision = _apply_if_allowed(decision, context=context)
    _sync_runtime_decisions(state)
    sync_timeline_for_state(state)
    return decision


def sync_decision_for_runtime(
    state: RuntimeState,
    *,
    decision_id: str,
) -> ExecutionDecision | None:
    decision = DecisionRegistry.default().get_decision(decision_id)
    if decision is None:
        return None
    _sync_runtime_decisions(state)
    sync_timeline_for_state(state)
    return decision


def build_execution_context(
    state: RuntimeState,
    *,
    task_id: str | None = None,
    session_id: str | None = None,
    retry_count: int | None = None,
    max_retries: int = 1,
    files_changed_count: int | None = None,
    confidence: float | None = None,
    validation_status: str | None = None,
    qa_status: str | None = None,
    missing_context: bool = False,
    task_too_large: bool = False,
    kilo_failed: bool = False,
    stuck_detected: bool = False,
    dead_lettered: bool = False,
    real_code_touched: bool = False,
    metadata: dict[str, Any] | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        workflow_run_id=state.run.run_id,
        session_id=session_id or _current_session_id(state),
        task_id=task_id or _current_task_id(state),
        autonomy_level=AutonomyLevel(str(state.metadata.get("autonomy_level", DEFAULT_AUTONOMY_LEVEL.value))),
        retry_count=retry_count if retry_count is not None else int(state.metadata.get("retry_attempts", 0)),
        max_retries=max_retries,
        files_changed_count=(
            files_changed_count
            if files_changed_count is not None
            else int(state.metadata.get("files_changed_count", 0))
        ),
        confidence=confidence,
        validation_status=validation_status,
        qa_status=qa_status,
        missing_context=missing_context,
        task_too_large=task_too_large,
        kilo_failed=kilo_failed,
        stuck_detected=stuck_detected,
        dead_lettered=dead_lettered,
        real_code_touched=real_code_touched,
        metadata=metadata or {},
    )


def _ensure_review_for_decision(
    state: RuntimeState,
    decision: ExecutionDecision,
) -> ExecutionDecision:
    if not decision.requires_human_review:
        return decision
    if decision.metadata.get("review_id"):
        return decision
    review = HumanReviewRegistry.default().create_review(
        review_type=ReviewType.EXECUTION_DECISION,
        target_id=decision.decision_id,
        target_type="ExecutionDecision",
        requested_by="intelligence",
        assigned_to="founder",
        notes=decision.reason,
        metadata={
            "run_id": state.run.run_id,
            "project": state.run.project,
            "issue_id": state.run.issue_id,
            "decision_type": decision.decision_type.value,
            "decision_status": decision.status.value,
            "autonomy_level": state.metadata.get("autonomy_level", DEFAULT_AUTONOMY_LEVEL.value),
            "session_id": decision.session_id,
            "task_id": decision.task_id,
        },
    )
    updated = decision.model_copy(
        update={
            "metadata": {
                **decision.metadata,
                "review_id": review.review_id,
                "review_type": review.review_type.value,
                "review_status": review.status.value,
            }
        }
    )
    return DecisionRegistry.default().save_decision(updated)


def _apply_if_allowed(
    decision: ExecutionDecision,
    *,
    context: ExecutionContext,
) -> ExecutionDecision:
    return DecisionRegistry.default().apply_decision(
        decision.decision_id,
        autonomy_level=context.autonomy_level,
        real_code_touched=context.real_code_touched,
        metadata={
            "autonomy_level": context.autonomy_level.value,
        },
    )


def _sync_runtime_decisions(state: RuntimeState) -> None:
    decisions = [
        decision.model_dump(mode="json")
        for decision in DecisionRegistry.default().list_decisions(workflow_run_id=state.run.run_id)
    ]
    latest = decisions[0] if decisions else None
    state.metadata["execution_decisions"] = decisions
    state.metadata["decision_count"] = len(decisions)
    state.metadata["autonomy_level"] = state.metadata.get("autonomy_level", DEFAULT_AUTONOMY_LEVEL.value)
    if latest is None:
        return
    state.metadata["decision_id"] = latest["decision_id"]
    state.metadata["decision_type"] = latest["decision_type"]
    state.metadata["decision_status"] = latest["status"]
    state.metadata["decision_confidence"] = latest["confidence"]
    state.metadata["decision_requires_human_review"] = latest["requires_human_review"]
    review_id = latest["metadata"].get("review_id")
    if review_id is not None:
        state.metadata["decision_review_id"] = review_id


def _current_session_id(state: RuntimeState) -> str | None:
    session_id = state.metadata.get("current_session_id")
    return str(session_id) if session_id else None


def _current_task_id(state: RuntimeState) -> str | None:
    current_task_package = state.artifacts.current_task_package
    if current_task_package is not None:
        return current_task_package.task_id
    task_id = state.metadata.get("current_queue_task_id")
    return str(task_id) if task_id else None
