from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from lummevia_economics import (
    CostControlDecision,
    CostEstimator,
    EconomicsRegistry,
    ExecutionBudget,
    UsageEstimate,
)


router = APIRouter(prefix="/economics", tags=["economics"])


def _registry() -> EconomicsRegistry:
    return EconomicsRegistry.default()


def _estimator() -> CostEstimator:
    return CostEstimator.default()


class BudgetCreateRequest(BaseModel):
    project: str = Field(min_length=1)
    workflow_run_id: str | None = None
    max_estimated_cost: float = Field(ge=0.0)
    max_model_calls: int = Field(ge=0)
    max_tokens_estimated: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EconomicsEvaluateRequest(BaseModel):
    project: str = Field(min_length=1)
    workflow_run_id: str | None = None
    budget_id: str | None = None
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    role: str = Field(min_length=1)
    operation_type: str = Field(min_length=1)
    prompt_length: int = Field(ge=0)
    output_length: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.get("/budgets", response_model=list[ExecutionBudget])
def list_budgets(project: str | None = None) -> list[ExecutionBudget]:
    return _registry().list_budgets(project=project)


@router.get("/budgets/{budget_id}", response_model=ExecutionBudget)
def get_budget(budget_id: str) -> ExecutionBudget:
    budget = _registry().get_budget(budget_id)
    if budget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution budget '{budget_id}' not found.",
        )
    return budget


@router.post("/budgets", response_model=ExecutionBudget)
def create_budget(request: BudgetCreateRequest) -> ExecutionBudget:
    return _registry().create_budget(
        ExecutionBudget(
            project=request.project,
            workflow_run_id=request.workflow_run_id,
            max_estimated_cost=request.max_estimated_cost,
            max_model_calls=request.max_model_calls,
            max_tokens_estimated=request.max_tokens_estimated,
            metadata=request.metadata,
        )
    )


@router.get("/usage", response_model=list[UsageEstimate])
def list_usage(
    project: str,
    workflow_run_id: str | None = None,
) -> list[UsageEstimate]:
    return _registry().get_usage_for_project(project, workflow_run_id=workflow_run_id)


@router.post("/evaluate", response_model=CostControlDecision)
def evaluate_cost(request: EconomicsEvaluateRequest) -> CostControlDecision:
    usage = _estimator().estimate_usage(
        project=request.project,
        workflow_run_id=request.workflow_run_id,
        provider=request.provider,
        model=request.model,
        role=request.role,
        operation_type=request.operation_type,
        prompt_length=request.prompt_length,
        output_length=request.output_length,
        metadata=request.metadata,
    )
    return _registry().evaluate_budget(
        project=request.project,
        budget_id=request.budget_id,
        workflow_run_id=request.workflow_run_id,
        pending_usage=usage,
    )
