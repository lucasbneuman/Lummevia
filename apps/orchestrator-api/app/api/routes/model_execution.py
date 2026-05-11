from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.model_execution import build_dry_run_model_executor
from lummevia_agents import ModelExecutionError, PromptExecutionRequest, PromptPipeline
from lummevia_core import AgentRole, BusinessBrief


router = APIRouter(prefix="/model-execution", tags=["model-execution"])


class PMDryRunRequest(BaseModel):
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)


class PMDryRunResponse(BaseModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    output: str = Field(min_length=1)
    raw_output: Any = None
    latency_ms: int = Field(ge=0)
    fallback_used: bool = False
    structured_output: BusinessBrief
    metadata: dict[str, Any] = Field(default_factory=dict)


@router.post("/pm/dry-run", response_model=PMDryRunResponse)
def pm_dry_run(request: PMDryRunRequest) -> PMDryRunResponse:
    try:
        model_executor = build_dry_run_model_executor(
            AgentRole.PM,
            deepseek=settings.deepseek,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    pipeline = PromptPipeline(model_executor=model_executor)

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
                },
            )
        )
    except ModelExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return PMDryRunResponse(
        provider=result.model_execution.metadata.get(
            "effective_provider",
            result.model_execution.provider,
        ),
        model=result.model_execution.metadata.get(
            "effective_model",
            result.model_execution.model,
        ),
        output=result.model_execution.output,
        raw_output=result.model_execution.raw_output,
        latency_ms=result.model_execution.latency_ms,
        fallback_used=result.model_execution.fallback_used,
        structured_output=result.structured_output,
        metadata=result.metadata,
    )
