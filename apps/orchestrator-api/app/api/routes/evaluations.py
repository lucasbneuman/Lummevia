from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.model_execution import build_dry_run_model_executor
from lummevia_agents import PromptPipeline
from lummevia_core import AgentRole
from lummevia_datasets import get_dataset
from lummevia_evaluations import RegressionRunResult
from lummevia_evaluations.regression import PromptRegressionRunner
from lummevia_integrations import PhoenixClient


router = APIRouter(prefix="/evaluations", tags=["evaluations"])


class PMRegressionRunRequest(BaseModel):
    project: str = Field(default="lummevia-os", min_length=1)
    dataset_id: str = Field(default="pm_business_brief_dataset", min_length=1)


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
