from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.routes import runtime as runtime_routes
from lummevia_learning import (
    LearningRegistry,
    LearningSignal,
    OperationalInsight,
    OptimizationRecommendation,
)
from lummevia_runtime import (
    accept_learning_recommendation,
    analyze_learning_for_project,
    analyze_learning_for_runtime,
    reject_learning_recommendation,
    sync_learning_for_runtime,
)


router = APIRouter(prefix="/learning", tags=["learning"])


class LearningAnalyzeRequest(BaseModel):
    project: str | None = None
    workflow_run_id: str | None = None
    issue_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class LearningDecisionRequest(BaseModel):
    notes: str | None = None
    assigned_to: str | None = None


class LearningAnalyzeResponse(BaseModel):
    signals: list[LearningSignal]
    insights: list[OperationalInsight]
    recommendations: list[OptimizationRecommendation]


@router.get("/signals", response_model=list[LearningSignal])
def list_learning_signals(project: str | None = None) -> list[LearningSignal]:
    return LearningRegistry.default().list_signals(project=project)


@router.get("/insights", response_model=list[OperationalInsight])
def list_learning_insights(project: str | None = None) -> list[OperationalInsight]:
    return LearningRegistry.default().list_insights(project=project)


@router.get("/recommendations", response_model=list[OptimizationRecommendation])
def list_learning_recommendations(
    project: str | None = None,
) -> list[OptimizationRecommendation]:
    return LearningRegistry.default().list_recommendations(project=project)


@router.post("/analyze", response_model=LearningAnalyzeResponse)
def analyze_learning(request: LearningAnalyzeRequest) -> LearningAnalyzeResponse:
    if request.workflow_run_id:
        try:
            state = runtime_routes.runtime_service.get_run(request.workflow_run_id)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Runtime run '{request.workflow_run_id}' not found.",
            ) from exc
        result = analyze_learning_for_runtime(
            state,
            context_overrides=request.context,
        )
        return LearningAnalyzeResponse.model_validate(result)

    if not request.project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project or workflow_run_id is required.",
        )
    result = analyze_learning_for_project(
        project=request.project,
        workflow_run_id=request.workflow_run_id,
        issue_id=request.issue_id,
        context_overrides=request.context,
    )
    return LearningAnalyzeResponse.model_validate(result)


@router.post(
    "/recommendations/{recommendation_id}/accept",
    response_model=OptimizationRecommendation,
)
def accept_recommendation(
    recommendation_id: str,
    request: LearningDecisionRequest,
) -> OptimizationRecommendation:
    recommendation = LearningRegistry.default().get_recommendation(recommendation_id)
    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation '{recommendation_id}' not found.",
        )
    updated = accept_learning_recommendation(
        recommendation_id,
        notes=request.notes,
        assigned_to=request.assigned_to,
    )
    _sync_runtime_if_possible(updated)
    return updated


@router.post(
    "/recommendations/{recommendation_id}/reject",
    response_model=OptimizationRecommendation,
)
def reject_recommendation(
    recommendation_id: str,
    request: LearningDecisionRequest,
) -> OptimizationRecommendation:
    recommendation = LearningRegistry.default().get_recommendation(recommendation_id)
    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation '{recommendation_id}' not found.",
        )
    updated = reject_learning_recommendation(
        recommendation_id,
        notes=request.notes,
        assigned_to=request.assigned_to,
    )
    _sync_runtime_if_possible(updated)
    return updated


def _sync_runtime_if_possible(recommendation: OptimizationRecommendation) -> None:
    run_id = recommendation.metadata.get("run_id")
    if not run_id:
        return
    try:
        state = runtime_routes.runtime_service.get_run(str(run_id))
    except Exception:
        return
    sync_learning_for_runtime(state)
