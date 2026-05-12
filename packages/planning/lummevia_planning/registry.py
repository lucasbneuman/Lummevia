from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from lummevia_planning.schemas import AdaptivePlan, AdaptivePlanStatus


class AdaptivePlanRegistry:
    _default_instance: ClassVar["AdaptivePlanRegistry" | None] = None

    def __init__(self) -> None:
        self._plans: dict[str, AdaptivePlan] = {}
        self._persistence = None

    @classmethod
    def default(cls) -> "AdaptivePlanRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._plans.clear()

    def configure_persistence(self, persistence) -> None:
        self._persistence = persistence

    def rehydrate(self, plans: list[AdaptivePlan]) -> None:
        self._plans = {plan.adaptive_plan_id: plan for plan in plans}

    def create_plan(self, plan: AdaptivePlan) -> AdaptivePlan:
        self._plans[plan.adaptive_plan_id] = plan
        self._persist_plan(plan)
        return plan

    def save_plan(self, plan: AdaptivePlan) -> AdaptivePlan:
        self._plans[plan.adaptive_plan_id] = plan
        self._persist_plan(plan)
        return plan

    def get_plan(self, adaptive_plan_id: str) -> AdaptivePlan | None:
        return self._plans.get(adaptive_plan_id)

    def list_plans(self, *, workflow_run_id: str | None = None) -> list[AdaptivePlan]:
        plans = self._plans.values()
        if workflow_run_id is not None:
            plans = (
                plan
                for plan in plans
                if plan.workflow_run_id == workflow_run_id
            )
        return sorted(
            plans,
            key=lambda item: (item.created_at, item.adaptive_plan_id),
            reverse=True,
        )

    def approve_plan(self, adaptive_plan_id: str, *, metadata: dict[str, Any] | None = None) -> AdaptivePlan:
        return self._update_status(
            adaptive_plan_id,
            status=AdaptivePlanStatus.APPROVED,
            metadata=metadata,
        )

    def reject_plan(self, adaptive_plan_id: str, *, metadata: dict[str, Any] | None = None) -> AdaptivePlan:
        return self._update_status(
            adaptive_plan_id,
            status=AdaptivePlanStatus.REJECTED,
            metadata=metadata,
        )

    def apply_plan(self, adaptive_plan_id: str, *, metadata: dict[str, Any] | None = None) -> AdaptivePlan:
        return self._update_status(
            adaptive_plan_id,
            status=AdaptivePlanStatus.APPLIED,
            metadata=metadata,
        )

    def _update_status(
        self,
        adaptive_plan_id: str,
        *,
        status: AdaptivePlanStatus,
        metadata: dict[str, Any] | None = None,
    ) -> AdaptivePlan:
        plan = self._plans[adaptive_plan_id]
        updated = plan.model_copy(
            update={
                "status": status,
                "updated_at": datetime.now(UTC),
                "metadata": {
                    **plan.metadata,
                    **(metadata or {}),
                },
            }
        )
        self._plans[adaptive_plan_id] = updated
        self._persist_plan(updated)
        return updated

    def _persist_plan(self, plan: AdaptivePlan) -> None:
        if self._persistence is None:
            return
        try:
            self._persistence.save_plan(plan)
        except Exception:
            return
