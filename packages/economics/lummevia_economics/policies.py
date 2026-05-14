from __future__ import annotations

from lummevia_economics.schemas import BudgetStatus, CostControlStatus


def evaluate_cost_control_status(usage_ratio: float) -> CostControlStatus:
    if usage_ratio > 1.0:
        return CostControlStatus.BLOCK
    if usage_ratio > 0.9:
        return CostControlStatus.DEGRADE
    if usage_ratio >= 0.7:
        return CostControlStatus.WARN
    return CostControlStatus.ALLOW


def budget_status_for_ratio(usage_ratio: float) -> BudgetStatus:
    if usage_ratio > 1.0:
        return BudgetStatus.EXCEEDED
    if usage_ratio >= 0.7:
        return BudgetStatus.WARNING
    return BudgetStatus.ACTIVE


def recommended_action_for_status(status: CostControlStatus) -> str:
    if status == CostControlStatus.ALLOW:
        return "continue_current_execution_profile"
    if status == CostControlStatus.WARN:
        return "switch_to_cost_optimized_strategy"
    if status == CostControlStatus.DEGRADE:
        return "recommend_lite_or_fake_models"
    return "block_real_provider_execution"
