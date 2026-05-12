from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.routes import runtime as runtime_routes
from lummevia_planning import (
    AdaptivePlan,
    AdaptivePlanRegistry,
    AdaptivePlanningContext,
    evaluate_adaptive_plan,
)
from lummevia_runtime.planning import sync_adaptive_plan_for_runtime


router = APIRouter(prefix="/planning", tags=["planning"])


def _get_registry() -> AdaptivePlanRegistry:
    return AdaptivePlanRegistry.default()


@router.get("/adaptive-plans", response_model=list[AdaptivePlan])
def list_adaptive_plans() -> list[AdaptivePlan]:
    return _get_registry().list_plans()


@router.get("/adaptive-plans/{adaptive_plan_id}", response_model=AdaptivePlan)
def get_adaptive_plan(adaptive_plan_id: str) -> AdaptivePlan:
    plan = _get_registry().get_plan(adaptive_plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Adaptive plan '{adaptive_plan_id}' not found.",
        )
    return plan


@router.post("/evaluate", response_model=AdaptivePlan)
def evaluate_planning(context: AdaptivePlanningContext) -> AdaptivePlan:
    return evaluate_adaptive_plan(context)


@router.post("/adaptive-plans/{adaptive_plan_id}/approve", response_model=AdaptivePlan)
def approve_adaptive_plan(adaptive_plan_id: str) -> AdaptivePlan:
    plan = _get_registry().get_plan(adaptive_plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Adaptive plan '{adaptive_plan_id}' not found.",
        )
    updated = _get_registry().approve_plan(
        adaptive_plan_id,
        metadata={"approved_via": "api"},
    )
    _sync_runtime(updated)
    return updated


@router.post("/adaptive-plans/{adaptive_plan_id}/reject", response_model=AdaptivePlan)
def reject_adaptive_plan(adaptive_plan_id: str) -> AdaptivePlan:
    plan = _get_registry().get_plan(adaptive_plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Adaptive plan '{adaptive_plan_id}' not found.",
        )
    updated = _get_registry().reject_plan(
        adaptive_plan_id,
        metadata={"rejected_via": "api"},
    )
    _sync_runtime(updated)
    return updated


def _sync_runtime(plan: AdaptivePlan) -> None:
    try:
        state = runtime_routes.runtime_service.get_run(plan.workflow_run_id)
    except Exception:
        return
    sync_adaptive_plan_for_runtime(state, adaptive_plan_id=plan.adaptive_plan_id)
