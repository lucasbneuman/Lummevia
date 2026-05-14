from __future__ import annotations

from collections.abc import Iterable
from typing import ClassVar

from lummevia_economics.policies import (
    budget_status_for_ratio,
    evaluate_cost_control_status,
    recommended_action_for_status,
)
from lummevia_economics.schemas import (
    CostControlDecision,
    CostControlStatus,
    ExecutionBudget,
    UsageEstimate,
)


class EconomicsRegistry:
    _default_instance: ClassVar["EconomicsRegistry | None"] = None

    def __init__(self) -> None:
        self._budgets: dict[str, ExecutionBudget] = {}
        self._usage: dict[str, UsageEstimate] = {}

    @classmethod
    def default(cls) -> "EconomicsRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._budgets.clear()
        self._usage.clear()

    def create_budget(self, budget: ExecutionBudget) -> ExecutionBudget:
        self._budgets[budget.budget_id] = budget
        return budget

    def get_budget(self, budget_id: str) -> ExecutionBudget | None:
        return self._budgets.get(budget_id)

    def list_budgets(self, *, project: str | None = None) -> list[ExecutionBudget]:
        budgets = list(self._budgets.values())
        if project is not None:
            budgets = [budget for budget in budgets if budget.project == project]
        return sorted(budgets, key=lambda item: (item.created_at, item.budget_id), reverse=True)

    def record_usage(self, usage: UsageEstimate) -> ExecutionBudget | None:
        self._usage[usage.usage_id] = usage
        budget = self._resolve_budget_for_usage(usage)
        if budget is None:
            return None
        updated_budget = budget.model_copy(
            update={
                "used_estimated_cost": round(budget.used_estimated_cost + usage.estimated_cost, 6),
                "used_model_calls": budget.used_model_calls + 1,
                "used_tokens_estimated": (
                    budget.used_tokens_estimated
                    + usage.estimated_input_tokens
                    + usage.estimated_output_tokens
                ),
            }
        )
        ratio = self._budget_usage_ratio(updated_budget)
        updated_budget = updated_budget.model_copy(
            update={"status": budget_status_for_ratio(ratio)}
        )
        self._budgets[updated_budget.budget_id] = updated_budget
        return updated_budget

    def get_usage_for_project(
        self,
        project: str,
        *,
        workflow_run_id: str | None = None,
    ) -> list[UsageEstimate]:
        usage = [item for item in self._usage.values() if item.project == project]
        if workflow_run_id is not None:
            usage = [item for item in usage if item.workflow_run_id == workflow_run_id]
        return sorted(usage, key=lambda item: (item.created_at, item.usage_id), reverse=True)

    def evaluate_budget(
        self,
        *,
        project: str,
        budget_id: str | None = None,
        pending_usage: UsageEstimate | None = None,
        workflow_run_id: str | None = None,
    ) -> CostControlDecision:
        budget = self._resolve_budget(project=project, budget_id=budget_id)
        if budget is None:
            return CostControlDecision(
                project=project,
                workflow_run_id=workflow_run_id,
                status=CostControlStatus.ALLOW,
                reason="No execution budget is configured for this project.",
                recommended_action=recommended_action_for_status(CostControlStatus.ALLOW),
                metadata={"no_budget": True},
            )
        budget_to_evaluate = budget
        if pending_usage is not None:
            budget_to_evaluate = budget.model_copy(
                update={
                    "used_estimated_cost": round(
                        budget.used_estimated_cost + pending_usage.estimated_cost, 6
                    ),
                    "used_model_calls": budget.used_model_calls + 1,
                    "used_tokens_estimated": (
                        budget.used_tokens_estimated
                        + pending_usage.estimated_input_tokens
                        + pending_usage.estimated_output_tokens
                    ),
                }
            )
        ratio = self._budget_usage_ratio(budget_to_evaluate)
        status = evaluate_cost_control_status(ratio)
        return CostControlDecision(
            project=project,
            workflow_run_id=workflow_run_id or budget.workflow_run_id,
            status=status,
            reason=self._build_reason(status, ratio, budget_to_evaluate),
            recommended_action=recommended_action_for_status(status),
            budget_id=budget.budget_id,
            metadata={
                "usage_ratio": round(ratio, 4),
                "budget_status": budget_status_for_ratio(ratio),
                "used_estimated_cost": budget_to_evaluate.used_estimated_cost,
                "used_model_calls": budget_to_evaluate.used_model_calls,
                "used_tokens_estimated": budget_to_evaluate.used_tokens_estimated,
                "max_estimated_cost": budget.max_estimated_cost,
                "max_model_calls": budget.max_model_calls,
                "max_tokens_estimated": budget.max_tokens_estimated,
            },
        )

    def active_budget_for_project(self, project: str) -> ExecutionBudget | None:
        budgets = self.list_budgets(project=project)
        for budget in budgets:
            if budget.status != "CLOSED":
                return budget
        return None

    def _resolve_budget_for_usage(self, usage: UsageEstimate) -> ExecutionBudget | None:
        budget_id = usage.metadata.get("budget_id")
        if isinstance(budget_id, str) and budget_id:
            return self.get_budget(budget_id)
        return self.active_budget_for_project(usage.project)

    def _resolve_budget(self, *, project: str, budget_id: str | None) -> ExecutionBudget | None:
        if budget_id:
            return self.get_budget(budget_id)
        return self.active_budget_for_project(project)

    def _budget_usage_ratio(self, budget: ExecutionBudget) -> float:
        ratios = list(
            self._non_zero_ratios(
                [
                    (budget.used_estimated_cost, budget.max_estimated_cost),
                    (budget.used_model_calls, budget.max_model_calls),
                    (budget.used_tokens_estimated, budget.max_tokens_estimated),
                ]
            )
        )
        if not ratios:
            return 0.0
        return max(ratios)

    def _non_zero_ratios(self, values: Iterable[tuple[float, float]]) -> Iterable[float]:
        for used, maximum in values:
            if maximum <= 0:
                continue
            yield float(used) / float(maximum)

    def _build_reason(
        self,
        status: CostControlStatus,
        ratio: float,
        budget: ExecutionBudget,
    ) -> str:
        percentage = round(ratio * 100, 2)
        return (
            f"Budget '{budget.budget_id}' for project '{budget.project}' is at "
            f"{percentage}% of configured limits, producing status '{status.value}'."
        )
