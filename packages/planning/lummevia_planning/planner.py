from __future__ import annotations

from lummevia_planning.mutation import build_split_task_proposals
from lummevia_planning.policies import (
    DEFAULT_HIGH_FILES_CHANGED_COUNT,
    DEFAULT_OVERSIZED_TASK_PACKAGE_THRESHOLD,
)
from lummevia_planning.schemas import (
    AdaptivePlan,
    AdaptivePlanningContext,
    MutationType,
    PlanMutation,
    QueueRecommendation,
)


def evaluate_adaptive_plan(context: AdaptivePlanningContext) -> AdaptivePlan:
    plan = AdaptivePlan(
        workflow_run_id=context.workflow_run_id,
        source_task_id=context.source_task_id,
        trigger_reason=context.trigger_reason,
        metadata={
            "project": context.project,
            "issue_id": context.issue_id,
            "files_changed_count": context.files_changed_count,
            "qa_fail_count": context.qa_fail_count,
            "retry_count": context.retry_count,
            "max_retries": context.max_retries,
            "missing_context": context.missing_context,
            "dependency_blocked": context.dependency_blocked,
            "validation_inconsistent": context.validation_inconsistent,
            "failed_validation": context.failed_validation,
            "dead_letter_risk": context.dead_letter_risk,
            "task_package_size": context.task_package_size,
            "blocked_dependencies": context.blocked_dependencies,
            **context.metadata,
        },
    )
    mutations: list[PlanMutation] = []
    queue_recommendations: list[QueueRecommendation] = []
    proposed_task_packages = []
    target = context.source_task_id or context.issue_id

    if context.missing_context:
        mutations.append(
            PlanMutation(
                adaptive_plan_id=plan.adaptive_plan_id,
                mutation_type=MutationType.REGENERATE_PROMPT,
                target=target,
                reason="The task is missing enough context to continue safely.",
            )
        )
        queue_recommendations.append(
            QueueRecommendation(
                action="HOLD_CURRENT_ITEM",
                target=target,
                reason="Prompt regeneration should happen before another execution attempt.",
            )
        )

    if context.failed_validation or context.validation_inconsistent:
        reason = (
            "Validation signals are inconsistent and require an explicit QA proposal."
            if context.validation_inconsistent
            else "Validation failed and the workflow should inject an explicit QA checkpoint."
        )
        mutations.append(
            PlanMutation(
                adaptive_plan_id=plan.adaptive_plan_id,
                mutation_type=MutationType.INSERT_QA,
                target=target,
                reason=reason,
            )
        )
        queue_recommendations.append(
            QueueRecommendation(
                action="INSERT_AFTER_CURRENT",
                target=target,
                reason=reason,
                metadata={"step_type": "qa"},
            )
        )

    if context.qa_fail_count >= 2:
        mutations.append(
            PlanMutation(
                adaptive_plan_id=plan.adaptive_plan_id,
                mutation_type=MutationType.INSERT_REVIEW,
                target=target,
                reason="QA failed repeatedly and requires a human review checkpoint.",
            )
        )

    if context.retry_count >= context.max_retries or context.dead_letter_risk:
        mutations.append(
            PlanMutation(
                adaptive_plan_id=plan.adaptive_plan_id,
                mutation_type=MutationType.ESCALATE_TASK,
                target=target,
                reason="Retry budget is exhausted or dead-letter risk is high for this task.",
            )
        )
        queue_recommendations.append(
            QueueRecommendation(
                action="ESCALATE",
                target=target,
                reason="This task should not continue without explicit human oversight.",
            )
        )

    if context.dependency_blocked:
        mutations.append(
            PlanMutation(
                adaptive_plan_id=plan.adaptive_plan_id,
                mutation_type=MutationType.REQUEUE_TASK,
                target=target,
                reason="A dependency is blocked and the current task should be requeued.",
                metadata={"blocked_dependencies": context.blocked_dependencies},
            )
        )
        queue_recommendations.append(
            QueueRecommendation(
                action="REQUEUE",
                target=target,
                reason="The task is waiting on dependency resolution.",
                metadata={"blocked_dependencies": context.blocked_dependencies},
            )
        )
        if context.blocked_dependencies:
            mutations.append(
                PlanMutation(
                    adaptive_plan_id=plan.adaptive_plan_id,
                    mutation_type=MutationType.REPLAN_DEPENDENCIES,
                    target=target,
                    reason="Dependency ordering should be reviewed before resuming execution.",
                    metadata={"blocked_dependencies": context.blocked_dependencies},
                )
            )

    if context.files_changed_count >= DEFAULT_HIGH_FILES_CHANGED_COUNT:
        mutation, split_proposals, recommendations = build_split_task_proposals(
            adaptive_plan_id=plan.adaptive_plan_id,
            source_task_id=target,
            reason="The detected diff is larger than the safe execution threshold.",
        )
        mutations.append(mutation)
        proposed_task_packages.extend(split_proposals)
        queue_recommendations.extend(recommendations)

    if context.task_package_size >= DEFAULT_OVERSIZED_TASK_PACKAGE_THRESHOLD:
        mutation, split_proposals, recommendations = build_split_task_proposals(
            adaptive_plan_id=plan.adaptive_plan_id,
            source_task_id=target,
            reason="The current TaskPackage is oversized and should be decomposed.",
        )
        mutations.append(mutation)
        proposed_task_packages.extend(split_proposals)
        queue_recommendations.extend(recommendations)

    plan.mutations = _dedupe_mutations(mutations)
    plan.proposed_task_packages = proposed_task_packages
    plan.queue_recommendations = queue_recommendations
    plan.metadata["mutation_count"] = len(plan.mutations)
    plan.metadata["mutation_types"] = [mutation.mutation_type.value for mutation in plan.mutations]
    plan.metadata["auto_apply_enabled"] = False
    return plan


def _dedupe_mutations(mutations: list[PlanMutation]) -> list[PlanMutation]:
    seen: set[tuple[str, str]] = set()
    deduped: list[PlanMutation] = []
    for mutation in mutations:
        key = (mutation.mutation_type.value, mutation.target)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(mutation)
    return deduped
