from __future__ import annotations

from lummevia_planning import AdaptivePlan

from lummevia_persistence.repositories.base import SnapshotRepository


class AdaptivePlanSnapshotRepository(SnapshotRepository):
    entity_type = "adaptive_plan"

    def save_plan(self, plan: AdaptivePlan):
        return self.save_snapshot(
            entity_type=self.entity_type,
            entity_id=plan.adaptive_plan_id,
            payload=plan.model_dump(mode="json"),
            metadata={
                "workflow_run_id": plan.workflow_run_id,
                "status": plan.status.value,
                "mutation_count": len(plan.mutations),
            },
        )

    def list_plans(self) -> list[AdaptivePlan]:
        return [
            AdaptivePlan.model_validate(snapshot.payload)
            for snapshot in self.list_latest_snapshots(self.entity_type)
        ]
