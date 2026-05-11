from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.model_execution import build_dry_run_model_executor
from lummevia_agents import PromptPipeline
from lummevia_core import AgentRole
from lummevia_datasets import get_dataset
from lummevia_evaluations import (
    PromptBaselineRegistry,
    PromptPromotionResult,
    RegressionRunResult,
)
from lummevia_evaluations.regression import PromptRegressionRunner
from lummevia_integrations import PhoenixClient


router = APIRouter(prefix="/evaluations", tags=["evaluations"])
PM_DATASET_BY_TEMPLATE = {
    "pm_business_brief": "pm_business_brief_dataset",
}


class PMRegressionRunRequest(BaseModel):
    project: str = Field(default="lummevia-os", min_length=1)
    dataset_id: str = Field(default="pm_business_brief_dataset", min_length=1)


class PMPromptPromotionRequest(BaseModel):
    template_id: str = Field(default="pm_business_brief", min_length=1)
    candidate_version: str = Field(min_length=1)
    promoted_by: str | None = None
    notes: str | None = None
    project: str = Field(default="lummevia-os", min_length=1)


class PMPromptPromotionResponse(BaseModel):
    promotion: PromptPromotionResult
    regression_run: RegressionRunResult
    baseline_version: str | None = None
    candidate_version: str = Field(min_length=1)
    regression_delta_score: float | None = None
    regression_delta_pass_rate: float | None = None
    regression_delta_latency: float | None = None
    failed_cases_delta: int | None = None


def _build_phoenix_client() -> PhoenixClient:
    return PhoenixClient(
        base_url=settings.phoenix.base_url,
        enabled=settings.phoenix.enabled,
        service_name=settings.app_name,
        environment=settings.app_env,
    )


def _observe_regression_run(
    *,
    regression_run_id: str,
    dataset_id: str,
    template_id: str,
    project: str,
    total_cases: int,
    passed_cases: int,
    failed_cases: int,
    avg_score: float,
    avg_latency_ms: float,
    status_value: str,
    error: str | None = None,
) -> None:
    attributes: dict[str, bool | int | float | str] = {
        "run_type": "pm_regression_run",
        "regression_run_id": regression_run_id,
        "dataset_id": dataset_id,
        "template_id": template_id,
        "project": project,
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "avg_score": avg_score,
        "avg_latency_ms": avg_latency_ms,
        "status": status_value,
    }
    if error is not None:
        attributes["error"] = error

    client = _build_phoenix_client()
    with client.start_as_current_span("pm_regression_run", attributes=attributes):
        client.force_flush()


def _observe_promotion_run(
    *,
    template_id: str,
    baseline_version: str | None,
    candidate_version: str,
    regression_run_id: str,
    project: str,
    promotion_status: str,
    regression_passed: bool,
    regression_delta_score: float | None,
    regression_delta_latency: float | None,
    regression_delta_pass_rate: float | None,
    failed_cases_delta: int | None,
    avg_score: float,
    avg_latency_ms: float,
    failed_cases: int,
    error: str | None = None,
) -> None:
    attributes: dict[str, bool | int | float | str] = {
        "run_type": "pm_prompt_promotion",
        "template_id": template_id,
        "candidate_version": candidate_version,
        "promotion_status": promotion_status,
        "regression_passed": regression_passed,
        "regression_run_id": regression_run_id,
        "project": project,
        "avg_score": avg_score,
        "avg_latency_ms": avg_latency_ms,
        "failed_cases": failed_cases,
    }
    if baseline_version is not None:
        attributes["baseline_version"] = baseline_version
    if regression_delta_score is not None:
        attributes["regression_delta_score"] = regression_delta_score
    if regression_delta_latency is not None:
        attributes["regression_delta_latency"] = regression_delta_latency
    if regression_delta_pass_rate is not None:
        attributes["regression_delta_pass_rate"] = regression_delta_pass_rate
    if failed_cases_delta is not None:
        attributes["failed_cases_delta"] = failed_cases_delta
    if error is not None:
        attributes["error"] = error

    client = _build_phoenix_client()
    with client.start_as_current_span("pm_prompt_promotion", attributes=attributes):
        client.force_flush()


def _get_baseline_registry() -> PromptBaselineRegistry:
    return PromptBaselineRegistry.default()


def _resolve_pm_dataset_id(template_id: str) -> str:
    try:
        return PM_DATASET_BY_TEMPLATE[template_id]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No PM regression dataset is registered for template '{template_id}'.",
        ) from exc


@router.post("/pm/regression-run", response_model=RegressionRunResult)
def pm_regression_run(request: PMRegressionRunRequest) -> RegressionRunResult:
    dataset = get_dataset(request.dataset_id)

    try:
        model_executor = build_dry_run_model_executor(
            AgentRole.PM,
            deepseek=settings.deepseek,
        )
    except ValueError as exc:
        _observe_regression_run(
            regression_run_id="UNAVAILABLE",
            dataset_id=request.dataset_id,
            template_id=dataset.template_id,
            project=request.project,
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            avg_score=0.0,
            avg_latency_ms=0.0,
            status_value="configuration_error",
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    runner = PromptRegressionRunner(
        pipeline=PromptPipeline(model_executor=model_executor),
    )

    try:
        result = runner.run_dataset(dataset, project=request.project)
    except Exception as exc:
        _observe_regression_run(
            regression_run_id="UNAVAILABLE",
            dataset_id=request.dataset_id,
            template_id=dataset.template_id,
            project=request.project,
            total_cases=0,
            passed_cases=0,
            failed_cases=0,
            avg_score=0.0,
            avg_latency_ms=0.0,
            status_value="failed",
            error=str(exc),
        )
        raise

    _observe_regression_run(
        regression_run_id=result.regression_run_id,
        dataset_id=result.dataset_id,
        template_id=result.template_id,
        project=request.project,
        total_cases=result.summary.total,
        passed_cases=result.summary.passed,
        failed_cases=result.summary.failed,
        avg_score=result.summary.avg_score,
        avg_latency_ms=result.summary.avg_latency_ms,
        status_value="completed",
    )
    return result


@router.post("/pm/promote", response_model=PMPromptPromotionResponse)
def pm_promote_prompt(
    request: PMPromptPromotionRequest,
) -> PMPromptPromotionResponse:
    dataset_id = _resolve_pm_dataset_id(request.template_id)
    dataset = get_dataset(dataset_id)

    try:
        model_executor = build_dry_run_model_executor(
            AgentRole.PM,
            deepseek=settings.deepseek,
        )
    except ValueError as exc:
        _observe_promotion_run(
            template_id=request.template_id,
            baseline_version=None,
            candidate_version=request.candidate_version,
            regression_run_id="UNAVAILABLE",
            project=request.project,
            promotion_status="CONFIGURATION_ERROR",
            regression_passed=False,
            regression_delta_score=None,
            regression_delta_latency=None,
            regression_delta_pass_rate=None,
            failed_cases_delta=None,
            avg_score=0.0,
            avg_latency_ms=0.0,
            failed_cases=0,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    runner = PromptRegressionRunner(
        pipeline=PromptPipeline(model_executor=model_executor),
    )
    baseline_registry = _get_baseline_registry()

    try:
        regression_run = runner.run_dataset(
            dataset,
            project=request.project,
            template_version=request.candidate_version,
        )
        comparison = baseline_registry.compare(
            template_id=request.template_id,
            candidate_version=request.candidate_version,
            current_summary=regression_run.summary,
        )
        promotion = baseline_registry.promote(
            template_id=request.template_id,
            candidate_version=request.candidate_version,
            regression_run=regression_run,
            promoted_by=request.promoted_by,
            notes=request.notes,
            metadata={
                "dataset_id": regression_run.dataset_id,
                "regression_run_id": regression_run.regression_run_id,
                "baseline_version": comparison.baseline_version,
                "candidate_version": request.candidate_version,
                "promotion_status": comparison.promotion_status.value,
                "regression_delta_score": comparison.delta_score,
                "regression_delta_latency": comparison.delta_latency_ms,
                "regression_delta_pass_rate": comparison.delta_pass_rate,
                "failed_cases_delta": comparison.failed_cases_delta,
            },
            comparison=comparison,
        )
    except Exception as exc:
        _observe_promotion_run(
            template_id=request.template_id,
            baseline_version=baseline_registry.get_active_version(request.template_id),
            candidate_version=request.candidate_version,
            regression_run_id="UNAVAILABLE",
            project=request.project,
            promotion_status="FAILED",
            regression_passed=False,
            regression_delta_score=None,
            regression_delta_latency=None,
            regression_delta_pass_rate=None,
            failed_cases_delta=None,
            avg_score=0.0,
            avg_latency_ms=0.0,
            failed_cases=0,
            error=str(exc),
        )
        raise

    _observe_promotion_run(
        template_id=request.template_id,
        baseline_version=comparison.baseline_version,
        candidate_version=request.candidate_version,
        regression_run_id=regression_run.regression_run_id,
        project=request.project,
        promotion_status=promotion.promotion_status.value,
        regression_passed=promotion.regression_passed,
        regression_delta_score=comparison.delta_score,
        regression_delta_latency=comparison.delta_latency_ms,
        regression_delta_pass_rate=comparison.delta_pass_rate,
        failed_cases_delta=comparison.failed_cases_delta,
        avg_score=regression_run.summary.avg_score,
        avg_latency_ms=regression_run.summary.avg_latency_ms,
        failed_cases=regression_run.summary.failed,
    )
    return PMPromptPromotionResponse(
        promotion=promotion,
        regression_run=regression_run,
        baseline_version=comparison.baseline_version,
        candidate_version=request.candidate_version,
        regression_delta_score=comparison.delta_score,
        regression_delta_pass_rate=comparison.delta_pass_rate,
        regression_delta_latency=comparison.delta_latency_ms,
        failed_cases_delta=comparison.failed_cases_delta,
    )
