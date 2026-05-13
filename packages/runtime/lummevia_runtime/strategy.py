from __future__ import annotations

from typing import Any

from lummevia_memory import MemoryCategory, ProjectMemoryRegistry
from lummevia_queue import TaskQueueRegistry
from lummevia_strategy import (
    ExecutionStrategy,
    ExecutionStrategyContext,
    RiskLevel,
    StrategyRegistry,
    StrategyType,
    evaluate_execution_strategy,
)

from lummevia_runtime.state import RuntimeState
from lummevia_runtime.timeline import sync_timeline_for_state


STRATEGY_ROLES = {"PM", "PO", "DEV", "QA"}


def initialize_strategy_runtime_state(state: RuntimeState) -> None:
    state.metadata.setdefault("execution_strategies", [])
    state.metadata.setdefault("strategy_count", 0)


def resolve_execution_strategy_for_step(
    state: RuntimeState,
    *,
    role: str,
    step_name: str,
    metadata: dict[str, Any] | None = None,
) -> ExecutionStrategy | None:
    if role not in STRATEGY_ROLES:
        return None
    context = build_strategy_context(
        state,
        role=role,
        step_name=step_name,
        execution_layer="WORKFLOW",
        execution_mode=str(state.metadata.get("execution_mode")) if state.metadata.get("execution_mode") else None,
        metadata=metadata,
    )
    strategy = StrategyRegistry.default().create_strategy(evaluate_execution_strategy(context))
    _sync_runtime_strategies(state)
    _propagate_strategy_to_current_queue_item(state)
    sync_timeline_for_state(state)
    return strategy


def resolve_execution_strategy_for_kilo(
    state: RuntimeState,
    *,
    role: str,
    step_name: str,
    execution_mode: str,
    sandbox_real: bool,
    metadata: dict[str, Any] | None = None,
) -> ExecutionStrategy:
    context = build_strategy_context(
        state,
        role=role,
        step_name=step_name,
        execution_layer="KILO",
        execution_mode=execution_mode,
        sandbox_real=sandbox_real,
        metadata=metadata,
    )
    strategy = StrategyRegistry.default().create_strategy(evaluate_execution_strategy(context))
    _sync_runtime_strategies(state)
    _propagate_strategy_to_current_queue_item(state)
    sync_timeline_for_state(state)
    return strategy


def sync_strategy_for_runtime(
    state: RuntimeState,
    *,
    strategy_id: str,
) -> ExecutionStrategy | None:
    strategy = StrategyRegistry.default().get_strategy(strategy_id)
    if strategy is None:
        return None
    _sync_runtime_strategies(state)
    _propagate_strategy_to_current_queue_item(state)
    sync_timeline_for_state(state)
    return strategy


def build_strategy_context(
    state: RuntimeState,
    *,
    role: str,
    step_name: str,
    execution_layer: str,
    execution_mode: str | None,
    sandbox_real: bool = False,
    metadata: dict[str, Any] | None = None,
) -> ExecutionStrategyContext:
    project = state.run.project
    latest_strategy = _latest_strategy(state)
    memory_registry = ProjectMemoryRegistry.default()
    qa_issues = memory_registry.search_by_category(project, MemoryCategory.QA_ISSUE)
    reviews = memory_registry.search_by_category(project, MemoryCategory.REVIEW_DECISION)
    business_decisions = memory_registry.search_by_category(project, MemoryCategory.BUSINESS_DECISION)
    return ExecutionStrategyContext(
        workflow_run_id=state.run.run_id,
        project=project,
        issue_id=state.run.issue_id,
        role=role,
        step_name=step_name,
        session_id=_current_session_id(state),
        task_id=_current_task_id(state),
        workflow_state=state.run.status.value,
        execution_layer=execution_layer,
        execution_mode=execution_mode,
        files_changed_count=int(state.metadata.get("files_changed_count", 0)),
        retry_count=int(state.metadata.get("retry_attempts", 0)),
        qa_fail_count=_qa_fail_count(state),
        prior_failure_count=int(state.metadata.get("decision_count", 0)),
        prior_qa_issue_count=len(qa_issues),
        prior_review_count=len(reviews),
        prior_dead_letter_count=int(state.metadata.get("dead_letter_count", 0)),
        confidence=_confidence_for_role(role),
        project_is_new=len(business_decisions) <= 1,
        history_is_stable=len(qa_issues) == 0 and len(reviews) > 0,
        sandbox_real=sandbox_real,
        cost_pressure_high=bool(state.metadata.get("cost_pressure_high", False)),
        dead_letter_risk=int(state.metadata.get("dead_letter_count", 0)) > 0,
        previous_strategy_type=(
            StrategyType(latest_strategy["strategy_type"])
            if latest_strategy is not None and latest_strategy.get("strategy_type")
            else None
        ),
        previous_risk_level=(
            RiskLevel(latest_strategy["risk_level"])
            if latest_strategy is not None and latest_strategy.get("risk_level")
            else None
        ),
        metadata={
            "simulation_only": execution_layer != "WORKFLOW" or not sandbox_real,
            "previous_qa_level": latest_strategy.get("qa_level") if latest_strategy is not None else None,
            "previous_sandbox_level": latest_strategy.get("sandbox_level") if latest_strategy is not None else None,
            **(metadata or {}),
        },
    )


def strategy_metadata(state: RuntimeState) -> dict[str, Any]:
    return {
        "strategy_id": state.metadata.get("strategy_id"),
        "strategy_type": state.metadata.get("strategy_type"),
        "risk_level": state.metadata.get("risk_level"),
        "qa_level": state.metadata.get("qa_level"),
        "sandbox_level": state.metadata.get("sandbox_level"),
        "selected_model": state.metadata.get("selected_model"),
        "selected_provider": state.metadata.get("selected_provider"),
        "execution_mode": state.metadata.get("execution_mode"),
    }


def _sync_runtime_strategies(state: RuntimeState) -> None:
    strategies = [
        strategy.model_dump(mode="json")
        for strategy in StrategyRegistry.default().list_strategies(workflow_run_id=state.run.run_id)
    ]
    latest = strategies[0] if strategies else None
    state.metadata["execution_strategies"] = strategies
    state.metadata["strategy_count"] = len(strategies)
    if latest is None:
        return
    state.metadata["strategy_id"] = latest["strategy_id"]
    state.metadata["strategy_type"] = latest["strategy_type"]
    state.metadata["risk_level"] = latest["risk_level"]
    state.metadata["qa_level"] = latest["qa_level"]
    state.metadata["sandbox_level"] = latest["sandbox_level"]
    state.metadata["selected_model"] = latest["selected_model"]
    state.metadata["selected_provider"] = latest["selected_provider"]
    state.metadata["execution_mode"] = latest["execution_mode"]
    state.metadata["strategy_reasoning"] = latest["reasoning"]


def _propagate_strategy_to_current_queue_item(state: RuntimeState) -> None:
    queue_snapshot = state.metadata.get("task_queue")
    queue_id = state.metadata.get("queue_id")
    current_queue_item_id = state.metadata.get("current_queue_item_id")
    if not current_queue_item_id:
        return
    if queue_id:
        queue = TaskQueueRegistry.default().get_queue(str(queue_id))
        current_item = None if queue is None else next(
            (item for item in queue.items if item.queue_item_id == current_queue_item_id),
            None,
        )
        if current_item is not None:
            TaskQueueRegistry.default().update_item_status(
                str(queue_id),
                str(current_queue_item_id),
                current_item.status,
                metadata={
                    **current_item.metadata,
                    **strategy_metadata(state),
                },
            )
        refreshed_queue = TaskQueueRegistry.default().get_queue(str(queue_id))
        if refreshed_queue is not None:
            state.metadata["task_queue"] = refreshed_queue.model_dump(mode="json")
            queue_snapshot = state.metadata["task_queue"]
    if not isinstance(queue_snapshot, dict):
        return
    for item in queue_snapshot.get("items", []):
        if not isinstance(item, dict) or item.get("queue_item_id") != current_queue_item_id:
            continue
        item.setdefault("metadata", {})
        item["metadata"].update(strategy_metadata(state))
        return


def _latest_strategy(state: RuntimeState) -> dict[str, Any] | None:
    strategies = state.metadata.get("execution_strategies", [])
    if not isinstance(strategies, list) or not strategies:
        return None
    latest = strategies[0]
    return latest if isinstance(latest, dict) else None


def _current_session_id(state: RuntimeState) -> str | None:
    value = state.metadata.get("current_session_id")
    return str(value) if value else None


def _current_task_id(state: RuntimeState) -> str | None:
    task_package = state.artifacts.current_task_package
    if task_package is not None:
        return task_package.task_id
    value = state.metadata.get("current_queue_task_id")
    return str(value) if value else None


def _qa_fail_count(state: RuntimeState) -> int:
    latest_validation = state.artifacts.validation_package
    if latest_validation is not None and latest_validation.status.value == "FAILED":
        return state.loop_count + 1
    return state.loop_count


def _confidence_for_role(role: str) -> float:
    if role == "PM":
        return 0.9
    if role == "PO":
        return 0.88
    if role == "QA":
        return 0.8
    return 0.84
