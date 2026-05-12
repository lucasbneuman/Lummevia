from __future__ import annotations

from lummevia_planning.schemas import AdaptivePlanStatus, MutationType


DEFAULT_HIGH_FILES_CHANGED_COUNT = 8
DEFAULT_OVERSIZED_TASK_PACKAGE_THRESHOLD = 12
DEFAULT_AUTO_APPLY_ENABLED = False
SENSITIVE_MUTATION_TYPES = {
    MutationType.SPLIT_TASK,
    MutationType.REPLAN_DEPENDENCIES,
    MutationType.ESCALATE_TASK,
}


def can_auto_apply_plan(*, status: AdaptivePlanStatus, auto_apply_enabled: bool = DEFAULT_AUTO_APPLY_ENABLED) -> bool:
    return auto_apply_enabled and status == AdaptivePlanStatus.APPROVED


def requires_human_review(mutation_type: MutationType) -> bool:
    return mutation_type in SENSITIVE_MUTATION_TYPES
