from __future__ import annotations

from typing import Any

from lummevia_agents import ModelExecutionResult
from lummevia_agents.prompts.pipeline import PromptExecutionResult

from lummevia_runtime.state import RuntimeState


_STATUS_ORDER = {
    "ALLOW": 0,
    "WARN": 1,
    "DEGRADE": 2,
    "BLOCK": 3,
}


def initialize_economics_runtime_state(state: RuntimeState) -> None:
    state.metadata.setdefault("budget_id", None)
    state.metadata.setdefault("cost_control_status", "ALLOW")
    state.metadata.setdefault("cost_recommendation", "continue_current_execution_profile")
    state.metadata.setdefault("estimated_cost_total", 0.0)
    state.metadata.setdefault("model_calls_count", 0)
    state.metadata.setdefault("tokens_estimated_total", 0)


def register_prompt_pipeline_cost(
    state: RuntimeState,
    *,
    step_name: str,
    pipeline_result: PromptExecutionResult,
) -> None:
    execution = pipeline_result.model_execution
    state.metadata["budget_id"] = execution.budget_id or state.metadata.get("budget_id")
    state.metadata["estimated_cost_total"] = float(
        pipeline_result.metadata.get(
            "estimated_cost_total",
            state.metadata.get("estimated_cost_total", 0.0),
        )
    )
    state.metadata["model_calls_count"] = int(
        pipeline_result.metadata.get(
            "model_calls_count",
            state.metadata.get("model_calls_count", 0),
        )
    )
    state.metadata["tokens_estimated_total"] = int(
        pipeline_result.metadata.get(
            "tokens_estimated_total",
            state.metadata.get("tokens_estimated_total", 0),
        )
    )
    cost_status = str(
        pipeline_result.metadata.get(
            "cost_control_status",
            execution.cost_control_status,
        )
    ).upper()
    if _STATUS_ORDER.get(cost_status, 0) >= _STATUS_ORDER.get(
        str(state.metadata.get("cost_control_status", "ALLOW")).upper(),
        0,
    ):
        state.metadata["cost_control_status"] = cost_status
        state.metadata["cost_recommendation"] = str(
            pipeline_result.metadata.get(
                "cost_recommendation",
                state.metadata.get("cost_recommendation", "continue_current_execution_profile"),
            )
        )
    state.metadata.setdefault("economics_by_step", {})[step_name] = _step_metadata(
        pipeline_result
    )


def register_model_execution_cost(
    state: RuntimeState,
    *,
    step_name: str,
    execution: ModelExecutionResult,
) -> None:
    _apply_cost_metadata(
        state,
        step_name=step_name,
        payload={
            "budget_id": execution.budget_id,
            "estimated_cost_total": execution.metadata.get("estimated_cost_total"),
            "model_calls_count": execution.metadata.get("model_calls_count"),
            "tokens_estimated_total": execution.metadata.get("tokens_estimated_total"),
            "cost_control_status": execution.cost_control_status,
            "cost_recommendation": execution.metadata.get("cost_recommendation"),
            "estimated_input_tokens": execution.estimated_input_tokens,
            "estimated_output_tokens": execution.estimated_output_tokens,
            "estimated_cost": execution.estimated_cost,
        },
    )


def _step_metadata(pipeline_result: PromptExecutionResult) -> dict[str, Any]:
    execution = pipeline_result.model_execution
    return {
        "budget_id": execution.budget_id,
        "estimated_input_tokens": execution.estimated_input_tokens,
        "estimated_output_tokens": execution.estimated_output_tokens,
        "estimated_cost": execution.estimated_cost,
        "cost_control_status": execution.cost_control_status,
        "cost_recommendation": pipeline_result.metadata.get("cost_recommendation"),
        "estimated_cost_total": pipeline_result.metadata.get("estimated_cost_total"),
        "model_calls_count": pipeline_result.metadata.get("model_calls_count"),
        "tokens_estimated_total": pipeline_result.metadata.get("tokens_estimated_total"),
    }


def _apply_cost_metadata(
    state: RuntimeState,
    *,
    step_name: str,
    payload: dict[str, Any],
) -> None:
    state.metadata["budget_id"] = payload.get("budget_id") or state.metadata.get("budget_id")
    if payload.get("estimated_cost_total") is not None:
        state.metadata["estimated_cost_total"] = float(payload["estimated_cost_total"])
    if payload.get("model_calls_count") is not None:
        state.metadata["model_calls_count"] = int(payload["model_calls_count"])
    if payload.get("tokens_estimated_total") is not None:
        state.metadata["tokens_estimated_total"] = int(payload["tokens_estimated_total"])
    cost_status = str(payload.get("cost_control_status", "ALLOW")).upper()
    if _STATUS_ORDER.get(cost_status, 0) >= _STATUS_ORDER.get(
        str(state.metadata.get("cost_control_status", "ALLOW")).upper(),
        0,
    ):
        state.metadata["cost_control_status"] = cost_status
        if payload.get("cost_recommendation") is not None:
            state.metadata["cost_recommendation"] = str(payload["cost_recommendation"])
    state.metadata.setdefault("economics_by_step", {})[step_name] = payload
