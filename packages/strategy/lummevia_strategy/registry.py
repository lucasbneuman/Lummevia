from __future__ import annotations

from typing import ClassVar

from lummevia_strategy.schemas import ExecutionStrategy


class StrategyRegistry:
    _default_instance: ClassVar["StrategyRegistry" | None] = None

    def __init__(self) -> None:
        self._strategies: dict[str, ExecutionStrategy] = {}

    @classmethod
    def default(cls) -> "StrategyRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._strategies.clear()

    def create_strategy(self, strategy: ExecutionStrategy) -> ExecutionStrategy:
        self._strategies[strategy.strategy_id] = strategy
        return strategy

    def save_strategy(self, strategy: ExecutionStrategy) -> ExecutionStrategy:
        self._strategies[strategy.strategy_id] = strategy
        return strategy

    def get_strategy(self, strategy_id: str) -> ExecutionStrategy | None:
        return self._strategies.get(strategy_id)

    def list_strategies(self, *, workflow_run_id: str | None = None) -> list[ExecutionStrategy]:
        strategies = self._strategies.values()
        if workflow_run_id is not None:
            strategies = (
                strategy
                for strategy in strategies
                if strategy.workflow_run_id == workflow_run_id
            )
        return sorted(
            strategies,
            key=lambda item: (item.created_at, item.strategy_id),
            reverse=True,
        )
