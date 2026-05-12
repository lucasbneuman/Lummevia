from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.routes import runtime as runtime_routes
from lummevia_intelligence import DecisionRegistry, ExecutionContext, ExecutionDecision, evaluate_execution
from lummevia_runtime.intelligence import sync_decision_for_runtime


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def _get_registry() -> DecisionRegistry:
    return DecisionRegistry.default()


@router.get("/decisions", response_model=list[ExecutionDecision])
def list_decisions() -> list[ExecutionDecision]:
    return _get_registry().list_decisions()


@router.get("/decisions/{decision_id}", response_model=ExecutionDecision)
def get_decision(decision_id: str) -> ExecutionDecision:
    decision = _get_registry().get_decision(decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution decision '{decision_id}' not found.",
        )
    return decision


@router.post("/decisions/{decision_id}/accept", response_model=ExecutionDecision)
def accept_decision(decision_id: str) -> ExecutionDecision:
    decision = _get_registry().get_decision(decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution decision '{decision_id}' not found.",
        )
    updated = _get_registry().accept_decision(decision_id)
    _sync_runtime(updated)
    return updated


@router.post("/decisions/{decision_id}/reject", response_model=ExecutionDecision)
def reject_decision(decision_id: str) -> ExecutionDecision:
    decision = _get_registry().get_decision(decision_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution decision '{decision_id}' not found.",
        )
    updated = _get_registry().reject_decision(decision_id)
    _sync_runtime(updated)
    return updated


@router.post("/evaluate", response_model=ExecutionDecision)
def evaluate_decision(context: ExecutionContext) -> ExecutionDecision:
    return evaluate_execution(context)


def _sync_runtime(decision: ExecutionDecision) -> None:
    try:
        state = runtime_routes.runtime_service.get_run(decision.workflow_run_id)
    except Exception:
        return
    sync_decision_for_runtime(state, decision_id=decision.decision_id)
