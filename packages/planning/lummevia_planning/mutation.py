from __future__ import annotations

from lummevia_planning.schemas import (
    PlanMutation,
    ProposedTaskPackage,
    QueueRecommendation,
)


def build_split_task_proposals(
    *,
    adaptive_plan_id: str,
    source_task_id: str,
    reason: str,
) -> tuple[PlanMutation, list[ProposedTaskPackage], list[QueueRecommendation]]:
    mutation = PlanMutation(
        adaptive_plan_id=adaptive_plan_id,
        mutation_type="SPLIT_TASK",
        target=source_task_id,
        reason=reason,
        metadata={
            "proposal_type": "controlled_graph_mutation",
        },
    )
    proposed = [
        ProposedTaskPackage(
            task_id=f"{source_task_id}-A",
            title=f"{source_task_id} split A",
            objective="Reduce the original task into a smaller first execution slice.",
            metadata={
                "derived_from": source_task_id,
                "proposal_reason": reason,
            },
        ),
        ProposedTaskPackage(
            task_id=f"{source_task_id}-B",
            title=f"{source_task_id} split B",
            objective="Continue the original task after the first split slice is validated.",
            dependencies=[f"{source_task_id}-A"],
            metadata={
                "derived_from": source_task_id,
                "proposal_reason": reason,
            },
        ),
    ]
    recommendations = [
        QueueRecommendation(
            action="ADD_ITEM",
            target=proposal.task_id,
            reason=reason,
            metadata={
                "derived_from": source_task_id,
                "dependencies": proposal.dependencies,
            },
        )
        for proposal in proposed
    ]
    return mutation, proposed, recommendations
