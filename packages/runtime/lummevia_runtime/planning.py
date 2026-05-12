from __future__ import annotations

from typing import Any

from lummevia_planning import (
    AdaptivePlan,
    AdaptivePlanRegistry,
    AdaptivePlanningContext,
    MutationType,
    evaluate_adaptive_plan,
    requires_human_review,
)
from lummevia_reviews import HumanReviewRegistry, ReviewType

from lummevia_runtime.state import RuntimeState
from lummevia_runtime.timeline import sync_timeline_for_state


def initialize_adaptive_planning_runtime_state(state: RuntimeState) -> None:
    state.metadata.setdefault("adaptive_plans", [])
    state.metadata.setdefault("adaptive_plan_count", 0)
    state.metadata.setdefault("mutation_count", 0)
    state.metadata.setdefault("mutation_types", [])
    state.metadata.setdefault("adaptive_plan_status", None)


def build_adaptive_planning_context(
    state: RuntimeState,
    *,
    trigger_reason: str,
    source_task_id: str | None = None,
    files_changed_count: int | None = None,
    qa_fail_count: int = 0,
    retry_count: int | None = None,
    max_retries: int = 1,
    missing_context: bool = False,
    dependency_blocked: bool = False,
    validation_inconsistent: bool = False,
    failed_validation: bool = False,
    dead_letter_risk: bool = False,
    task_package_size: int | None = None,
    blocked_dependencies: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AdaptivePlanningContext:
    current_task_id = source_task_id or _current_task_id(state)
    return AdaptivePlanningContext(
        workflow_run_id=state.run.run_id,
        project=state.run.project,
        issue_id=state.run.issue_id,
        source_task_id=current_task_id,
        trigger_reason=trigger_reason,
        files_changed_count=(
            files_changed_count
            if files_changed_count is not None
            else int(state.metadata.get("files_changed_count", 0))
        ),
        qa_fail_count=qa_fail_count,
        retry_count=(
            retry_count
            if retry_count is not None
            else int(state.metadata.get("retry_attempts", 0))
        ),
        max_retries=max_retries,
        missing_context=missing_context,
        dependency_blocked=dependency_blocked,
        validation_inconsistent=validation_inconsistent,
        failed_validation=failed_validation,
        dead_letter_risk=dead_letter_risk,
        task_package_size=(
            task_package_size
            if task_package_size is not None
            else _task_package_size(state)
        ),
        blocked_dependencies=blocked_dependencies or [],
        metadata=metadata or {},
    )


def propose_adaptive_plan(
    state: RuntimeState,
    *,
    context: AdaptivePlanningContext,
) -> AdaptivePlan:
    registry = AdaptivePlanRegistry.default()
    plan = registry.create_plan(evaluate_adaptive_plan(context))
    plan = _ensure_review_for_sensitive_mutations(state, plan)
    _sync_runtime_plans(state)
    sync_timeline_for_state(state)
    return plan


def sync_adaptive_plan_for_runtime(
    state: RuntimeState,
    *,
    adaptive_plan_id: str,
) -> AdaptivePlan | None:
    plan = AdaptivePlanRegistry.default().get_plan(adaptive_plan_id)
    if plan is None:
        return None
    _sync_runtime_plans(state)
    sync_timeline_for_state(state)
    return plan


def _ensure_review_for_sensitive_mutations(
    state: RuntimeState,
    plan: AdaptivePlan,
) -> AdaptivePlan:
    if plan.metadata.get("review_id"):
        return plan
    mutation_types = {mutation.mutation_type for mutation in plan.mutations}
    if not any(requires_human_review(mutation_type) for mutation_type in mutation_types):
        return plan
    review = HumanReviewRegistry.default().create_review(
        review_type=ReviewType.ADAPTIVE_PLAN,
        target_id=plan.adaptive_plan_id,
        target_type="AdaptivePlan",
        requested_by="planning",
        assigned_to="founder",
        notes=plan.trigger_reason,
        metadata={
            "run_id": state.run.run_id,
            "project": state.run.project,
            "issue_id": state.run.issue_id,
            "mutation_types": [mutation.mutation_type.value for mutation in plan.mutations],
            "source_task_id": plan.source_task_id,
            "adaptive_plan_status": plan.status.value,
        },
    )
    updated = plan.model_copy(
        update={
            "metadata": {
                **plan.metadata,
                "review_id": review.review_id,
                "review_type": review.review_type.value,
                "review_status": review.status.value,
            }
        }
    )
    return AdaptivePlanRegistry.default().save_plan(updated)


def _sync_runtime_plans(state: RuntimeState) -> None:
    plans = [
        plan.model_dump(mode="json")
        for plan in AdaptivePlanRegistry.default().list_plans(workflow_run_id=state.run.run_id)
    ]
    latest = plans[0] if plans else None
    state.metadata["adaptive_plans"] = plans
    state.metadata["adaptive_plan_count"] = len(plans)
    state.metadata["mutation_count"] = sum(len(plan.get("mutations", [])) for plan in plans)
    state.metadata["mutation_types"] = sorted(
        {
            mutation.get("mutation_type")
            for plan in plans
            for mutation in plan.get("mutations", [])
            if mutation.get("mutation_type") is not None
        }
    )
    if latest is None:
        return
    state.metadata["adaptive_plan_id"] = latest["adaptive_plan_id"]
    state.metadata["adaptive_plan_status"] = latest["status"]
    state.metadata["replanning_trigger"] = latest["trigger_reason"]
    state.metadata["latest_adaptive_plan"] = latest
    review_id = latest.get("metadata", {}).get("review_id")
    if review_id is not None:
        state.metadata["adaptive_plan_review_id"] = review_id


def _current_task_id(state: RuntimeState) -> str | None:
    current_task_package = state.artifacts.current_task_package
    if current_task_package is not None:
        return current_task_package.task_id
    current_task_id = state.metadata.get("current_queue_task_id")
    return str(current_task_id) if current_task_id else None


def _task_package_size(state: RuntimeState) -> int:
    task_package = state.artifacts.current_task_package
    if task_package is None:
        return 0
    return (
        len(task_package.context_refs)
        + len(task_package.acceptance_criteria)
        + len(task_package.constraints)
        + len(task_package.expected_artifacts)
    )
