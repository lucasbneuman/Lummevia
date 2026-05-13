from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from lummevia_strategy import (
    ExecutionStrategy,
    ExecutionStrategyContext,
    StrategyRegistry,
    evaluate_execution_strategy,
)


router = APIRouter(prefix="/strategy", tags=["strategy"])


def _get_registry() -> StrategyRegistry:
    return StrategyRegistry.default()


@router.get("", response_model=list[ExecutionStrategy])
def list_strategies() -> list[ExecutionStrategy]:
    return _get_registry().list_strategies()


@router.get("/{strategy_id}", response_model=ExecutionStrategy)
def get_strategy(strategy_id: str) -> ExecutionStrategy:
    strategy = _get_registry().get_strategy(strategy_id)
    if strategy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution strategy '{strategy_id}' not found.",
        )
    return strategy


@router.post("/evaluate", response_model=ExecutionStrategy)
def evaluate_strategy(context: ExecutionStrategyContext) -> ExecutionStrategy:
    return evaluate_execution_strategy(context)
