from __future__ import annotations

from time import perf_counter
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.model_execution import build_dry_run_model_executor
from lummevia_agents import ModelExecutionError, PromptExecutionRequest, PromptPipeline
from lummevia_core import AgentRole, BusinessBrief
from lummevia_evaluations import EvaluationStatus, PromptEvaluation, evaluate_prompt_execution
from lummevia_integrations import PhoenixClient
from model_router import RoutingRequest, resolve_model


router = APIRouter(prefix="/model-execution", tags=["model-execution"])


class PMDryRunRequest(BaseModel):
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)


class PMDryRunResponse(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    resolved_provider: str = Field(min_length=1)
    resolved_model: str = Field(min_length=1)
    effective_provider: str = Field(min_length=1)
    effective_model: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    prompt_hash: str = Field(min_length=64, max_length=64)
    output: str = Field(min_length=1)
    raw_output: Any = None
    latency_ms: int = Field(ge=0)
    fallback_used: bool = False
    estimated_input_tokens: int = Field(ge=0)
    estimated_output_tokens: int = Field(ge=0)
    estimated_cost: float = Field(ge=0.0)
    cost_control_status: str = Field(min_length=1)
    budget_id: str | None = None
    structured_output: BusinessBrief
    evaluation_id: str | None = None
    evaluation_status: EvaluationStatus = EvaluationStatus.PENDING
    evaluation: PromptEvaluation | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _build_phoenix_client() -> PhoenixClient:
    return PhoenixClient(
        base_url=settings.phoenix.base_url,
        enabled=settings.phoenix.enabled,
        api_key=settings.phoenix.api_key,
        service_name=settings.app_name,
        environment=settings.app_env,
    )


def _observe_pm_dry_run(
    *,
    project: str,
    issue_id: str,
    resolved_provider: str,
    resolved_model: str,
    effective_provider: str,
    effective_model: str,
    template_id: str | None,
    template_version: str | None,
    prompt_hash: str | None,
    evaluation_status: str | None,
    evaluation_score: float | None,
    latency_ms: int,
    fallback_used: bool,
    status_value: str,
    budget_id: str | None = None,
    estimated_cost: float | None = None,
    estimated_cost_total: float | None = None,
    model_calls_count: int | None = None,
    tokens_estimated_total: int | None = None,
    cost_control_status: str | None = None,
    cost_recommendation: str | None = None,
    error: str | None = None,
) -> None:
    attributes: dict[str, bool | int | str] = {
        "run_type": "pm_dry_run",
        "project": project,
        "issue_id": issue_id,
        "resolved_provider": resolved_provider,
        "resolved_model": resolved_model,
        "effective_provider": effective_provider,
        "effective_model": effective_model,
        "latency_ms": latency_ms,
        "fallback_used": fallback_used,
        "status": status_value,
    }
    if template_id is not None:
        attributes["template_id"] = template_id
    if template_version is not None:
        attributes["template_version"] = template_version
    if prompt_hash is not None:
        attributes["prompt_hash"] = prompt_hash
    if evaluation_status is not None:
        attributes["evaluation_status"] = evaluation_status
    if evaluation_score is not None:
        attributes["evaluation_score"] = evaluation_score
    if budget_id is not None:
        attributes["budget_id"] = budget_id
    if estimated_cost is not None:
        attributes["estimated_cost"] = estimated_cost
    if estimated_cost_total is not None:
        attributes["estimated_cost_total"] = estimated_cost_total
    if model_calls_count is not None:
        attributes["model_calls_count"] = model_calls_count
    if tokens_estimated_total is not None:
        attributes["tokens_estimated_total"] = tokens_estimated_total
    if cost_control_status is not None:
        attributes["cost_control_status"] = cost_control_status
    if cost_recommendation is not None:
        attributes["cost_recommendation"] = cost_recommendation
    if error is not None:
        attributes["error"] = error

    client = _build_phoenix_client()
    with client.start_as_current_span("pm_dry_run", attributes=attributes):
        client.force_flush()


@router.post("/pm/dry-run", response_model=PMDryRunResponse)
def pm_dry_run(request: PMDryRunRequest) -> PMDryRunResponse:
    resolution = resolve_model(
        RoutingRequest(
            role=AgentRole.PM,
            project=request.project,
        )
    )

    try:
        model_executor = build_dry_run_model_executor(
            AgentRole.PM,
            deepseek=settings.deepseek,
        )
    except ValueError as exc:
        _observe_pm_dry_run(
            project=request.project,
            issue_id=request.issue_id,
            resolved_provider=resolution.provider.value,
            resolved_model=resolution.model,
            effective_provider="UNAVAILABLE",
            effective_model="UNAVAILABLE",
            template_id=None,
            template_version=None,
            prompt_hash=None,
            evaluation_status=None,
            evaluation_score=None,
            latency_ms=0,
            fallback_used=False,
            status_value="configuration_error",
            budget_id=None,
            estimated_cost=None,
            estimated_cost_total=None,
            model_calls_count=None,
            tokens_estimated_total=None,
            cost_control_status=None,
            cost_recommendation=None,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    pipeline = PromptPipeline(model_executor=model_executor)
    started_at = perf_counter()

    try:
        result = pipeline.execute(
            PromptExecutionRequest(
                role=AgentRole.PM,
                project=request.project,
                issue_id=request.issue_id,
                target_artifact="BusinessBrief",
                available_artifacts={
                    "founder_input": {
                        "summary": request.prompt,
                    }
                },
                metadata={
                    "dry_run": True,
                    "requested_prompt": request.prompt,
                    "operation_type": "pm_dry_run",
                    "issue_id": request.issue_id,
                },
            )
        )
    except ModelExecutionError as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
        _observe_pm_dry_run(
            project=request.project,
            issue_id=request.issue_id,
            resolved_provider=resolution.provider.value,
            resolved_model=resolution.model,
            effective_provider="UNAVAILABLE",
            effective_model="UNAVAILABLE",
            template_id=None,
            template_version=None,
            prompt_hash=None,
            evaluation_status=None,
            evaluation_score=None,
            latency_ms=latency_ms,
            fallback_used=False,
            status_value="failed",
            budget_id=None,
            estimated_cost=None,
            estimated_cost_total=None,
            model_calls_count=None,
            tokens_estimated_total=None,
            cost_control_status=None,
            cost_recommendation=None,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    evaluation = evaluate_prompt_execution(result)
    result_metadata = dict(result.metadata)
    result_metadata.update(
        {
            "evaluation_id": evaluation.evaluation_id,
            "evaluation_status": evaluation.status,
            "evaluation_score": evaluation.score,
            "evaluation": evaluation.model_dump(mode="json"),
        }
    )

    _observe_pm_dry_run(
        project=request.project,
        issue_id=request.issue_id,
        resolved_provider=result.model_execution.resolved_provider,
        resolved_model=result.model_execution.resolved_model,
        effective_provider=result.model_execution.effective_provider,
        effective_model=result.model_execution.effective_model,
        template_id=result.template_id,
        template_version=result.template_version,
        prompt_hash=result.prompt_hash,
        evaluation_status=evaluation.status,
        evaluation_score=evaluation.score,
        latency_ms=result.model_execution.latency_ms,
        fallback_used=result.model_execution.fallback_used,
        status_value="completed",
        budget_id=result.model_execution.budget_id,
        estimated_cost=result.model_execution.estimated_cost,
        estimated_cost_total=result.model_execution.metadata.get("estimated_cost_total"),
        model_calls_count=result.model_execution.metadata.get("model_calls_count"),
        tokens_estimated_total=result.model_execution.metadata.get("tokens_estimated_total"),
        cost_control_status=result.model_execution.cost_control_status,
        cost_recommendation=result.model_execution.metadata.get("cost_recommendation"),
    )

    return PMDryRunResponse(
        provider=result.model_execution.provider,
        model=result.model_execution.model,
        resolved_provider=result.model_execution.resolved_provider,
        resolved_model=result.model_execution.resolved_model,
        effective_provider=result.model_execution.effective_provider,
        effective_model=result.model_execution.effective_model,
        template_id=result.template_id,
        template_version=result.template_version,
        prompt_hash=result.prompt_hash,
        output=result.model_execution.output,
        raw_output=result.model_execution.raw_output,
        latency_ms=result.model_execution.latency_ms,
        fallback_used=result.model_execution.fallback_used,
        estimated_input_tokens=result.model_execution.estimated_input_tokens,
        estimated_output_tokens=result.model_execution.estimated_output_tokens,
        estimated_cost=result.model_execution.estimated_cost,
        cost_control_status=result.model_execution.cost_control_status,
        budget_id=result.model_execution.budget_id,
        structured_output=result.structured_output,
        evaluation_id=evaluation.evaluation_id,
        evaluation_status=evaluation.status,
        evaluation=evaluation,
        metadata=result_metadata,
    )
