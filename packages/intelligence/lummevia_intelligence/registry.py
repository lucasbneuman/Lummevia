from __future__ import annotations

from typing import Any, ClassVar

from lummevia_intelligence.policies import can_apply_decision
from lummevia_intelligence.schemas import (
    AutonomyLevel,
    DecisionStatus,
    ExecutionDecision,
)


class DecisionRegistry:
    _default_instance: ClassVar["DecisionRegistry" | None] = None

    def __init__(self) -> None:
        self._decisions: dict[str, ExecutionDecision] = {}

    @classmethod
    def default(cls) -> "DecisionRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._decisions.clear()

    def create_decision(self, decision: ExecutionDecision) -> ExecutionDecision:
        self._decisions[decision.decision_id] = decision
        return decision

    def save_decision(self, decision: ExecutionDecision) -> ExecutionDecision:
        self._decisions[decision.decision_id] = decision
        return decision

    def get_decision(self, decision_id: str) -> ExecutionDecision | None:
        return self._decisions.get(decision_id)

    def list_decisions(self, *, workflow_run_id: str | None = None) -> list[ExecutionDecision]:
        decisions = self._decisions.values()
        if workflow_run_id is not None:
            decisions = (
                decision
                for decision in decisions
                if decision.workflow_run_id == workflow_run_id
            )
        return sorted(
            decisions,
            key=lambda item: (item.created_at, item.decision_id),
            reverse=True,
        )

    def accept_decision(self, decision_id: str, *, metadata: dict[str, Any] | None = None) -> ExecutionDecision:
        return self._update_status(decision_id, status=DecisionStatus.ACCEPTED, metadata=metadata)

    def reject_decision(self, decision_id: str, *, metadata: dict[str, Any] | None = None) -> ExecutionDecision:
        return self._update_status(decision_id, status=DecisionStatus.REJECTED, metadata=metadata)

    def apply_decision(
        self,
        decision_id: str,
        *,
        autonomy_level: AutonomyLevel,
        real_code_touched: bool,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionDecision:
        decision = self._decisions[decision_id]
        if not can_apply_decision(
            autonomy_level=autonomy_level,
            decision_type=decision.decision_type,
            real_code_touched=real_code_touched,
        ):
            return self._update_status(
                decision_id,
                status=decision.status,
                metadata={
                    **(metadata or {}),
                    "apply_blocked": True,
                    "autonomy_level": autonomy_level.value,
                },
            )
        return self._update_status(
            decision_id,
            status=DecisionStatus.APPLIED,
            metadata={
                **(metadata or {}),
                "applied_by_policy": True,
                "autonomy_level": autonomy_level.value,
            },
        )

    def _update_status(
        self,
        decision_id: str,
        *,
        status: DecisionStatus,
        metadata: dict[str, Any] | None = None,
    ) -> ExecutionDecision:
        decision = self._decisions[decision_id]
        updated = decision.model_copy(
            update={
                "status": status,
                "metadata": {
                    **decision.metadata,
                    **(metadata or {}),
                },
            }
        )
        self._decisions[decision_id] = updated
        return updated
