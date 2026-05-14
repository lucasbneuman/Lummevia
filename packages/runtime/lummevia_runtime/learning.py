from __future__ import annotations

from statistics import mean
from typing import Any

from lummevia_evaluations import EvaluationStatus, PromptEvaluationRegistry
from lummevia_learning import (
    LearningAnalysisContext,
    LearningAnalyzer,
    LearningRegistry,
    OperationalInsight,
    OptimizationRecommendation,
    RecommendationStatus,
    generate_recommendations,
    highest_severity,
)
from lummevia_memory import (
    MemoryCategory,
    MemorySourceType,
    ProjectMemoryRegistry,
    build_project_memory_metadata,
)
from lummevia_reviews import HumanReviewRegistry, ReviewDecision, ReviewType

from lummevia_runtime.state import RuntimeState
from lummevia_runtime.timeline import sync_timeline_for_state


def initialize_learning_runtime_state(state: RuntimeState) -> None:
    state.metadata.setdefault("learning_signal_ids", [])
    state.metadata.setdefault("learning_signals", [])
    state.metadata.setdefault("learning_signal_count", 0)
    state.metadata.setdefault("insight_ids", [])
    state.metadata.setdefault("insights", [])
    state.metadata.setdefault("insight_count", 0)
    state.metadata.setdefault("recommendation_ids", [])
    state.metadata.setdefault("recommendations", [])
    state.metadata.setdefault("recommendation_count", 0)
    state.metadata.setdefault("learning_severity", None)
    state.metadata.setdefault("recommendation_type", None)


def analyze_learning_for_runtime(
    state: RuntimeState,
    *,
    context_overrides: dict[str, Any] | None = None,
) -> dict[str, list]:
    context = build_learning_analysis_context(
        state,
        overrides=context_overrides,
    )
    analyzer = LearningAnalyzer()
    signals, insights = analyzer.analyze(context)
    registry = LearningRegistry.default()
    stored_signals = [registry.add_signal(signal) for signal in signals]
    stored_insights = [registry.add_insight(insight) for insight in insights]
    stored_recommendations = [
        registry.add_recommendation(recommendation)
        for recommendation in generate_recommendations(
            project=state.run.project,
            insights=stored_insights,
            metadata={
                "run_id": state.run.run_id,
                "issue_id": state.run.issue_id,
                "source_type": context.source_type,
                "source_id": context.source_id,
            },
        )
    ]
    _create_memory_for_insights(state, stored_insights)
    _create_reviews_for_recommendations(state, stored_recommendations)
    sync_learning_for_runtime(state)
    return {
        "signals": stored_signals,
        "insights": stored_insights,
        "recommendations": stored_recommendations,
    }


def analyze_learning_for_project(
    *,
    project: str,
    workflow_run_id: str | None = None,
    issue_id: str | None = None,
    context_overrides: dict[str, Any] | None = None,
) -> dict[str, list]:
    context = LearningAnalysisContext(
        project=project,
        source_type="MANUAL_ANALYSIS",
        source_id=workflow_run_id or issue_id or "manual-analysis",
        metadata={
            "run_id": workflow_run_id,
            "issue_id": issue_id,
            **(context_overrides or {}),
        },
        **_context_values_from_overrides(context_overrides),
    )
    analyzer = LearningAnalyzer()
    signals, insights = analyzer.analyze(context)
    registry = LearningRegistry.default()
    stored_insights = [registry.add_insight(insight) for insight in insights]
    stored_recommendations = [
        registry.add_recommendation(recommendation)
        for recommendation in generate_recommendations(
            project=project,
            insights=stored_insights,
            metadata={
                "run_id": workflow_run_id,
                "issue_id": issue_id,
                "source_type": context.source_type,
                "source_id": context.source_id,
            },
        )
    ]
    _create_memory_for_project_insights(
        project=project,
        workflow_run_id=workflow_run_id,
        issue_id=issue_id,
        insights=stored_insights,
    )
    _create_reviews_for_project_recommendations(
        project=project,
        workflow_run_id=workflow_run_id,
        issue_id=issue_id,
        recommendations=stored_recommendations,
    )
    return {
        "signals": [registry.add_signal(signal) for signal in signals],
        "insights": stored_insights,
        "recommendations": stored_recommendations,
    }


def build_learning_analysis_context(
    state: RuntimeState,
    *,
    overrides: dict[str, Any] | None = None,
) -> LearningAnalysisContext:
    project = state.run.project
    review_payloads = state.metadata.get("review_by_step", {})
    needs_review_count = 0
    if isinstance(review_payloads, dict):
        needs_review_count += sum(
            1
            for payload in review_payloads.values()
            if isinstance(payload, dict)
            and payload.get("review_status") in {"PENDING", "IN_REVIEW"}
        )

    evaluations = [
        evaluation
        for evaluation in PromptEvaluationRegistry.default().list_evaluations()
        if evaluation.metadata.get("project") == project
    ]
    needs_review_count += sum(
        1 for evaluation in evaluations if evaluation.status == EvaluationStatus.NEEDS_REVIEW
    )
    low_prompt_score_count = sum(
        1
        for evaluation in evaluations
        if evaluation.status in {EvaluationStatus.FAILED, EvaluationStatus.NEEDS_REVIEW}
        or ((evaluation.score or 0.0) < 0.7)
    )
    qa_failure_count = len(
        ProjectMemoryRegistry.default().search_by_category(project, MemoryCategory.QA_ISSUE)
    )
    strategy_snapshots = state.metadata.get("execution_strategies", [])
    strategy_count = 0
    recovery_strategy_count = 0
    if isinstance(strategy_snapshots, list):
        strategy_count = len(strategy_snapshots)
        recovery_strategy_count = sum(
            1
            for item in strategy_snapshots
            if isinstance(item, dict) and item.get("strategy_type") == "RECOVERY"
        )
    return LearningAnalysisContext(
        project=project,
        source_type=str((overrides or {}).get("source_type", "RUNTIME")),
        source_id=str((overrides or {}).get("source_id", state.run.run_id)),
        qa_failure_count=int((overrides or {}).get("qa_failure_count", qa_failure_count)),
        retry_count=int((overrides or {}).get("retry_count", state.metadata.get("retry_attempts", 0))),
        estimated_cost_total=float(
            (overrides or {}).get(
                "estimated_cost_total",
                state.metadata.get("estimated_cost_total", 0.0),
            )
        ),
        cost_control_status=str(
            (overrides or {}).get(
                "cost_control_status",
                state.metadata.get("cost_control_status", "ALLOW"),
            )
        ),
        avg_latency_ms=float(
            (overrides or {}).get(
                "avg_latency_ms",
                _average_latency_ms(state),
            )
        ),
        needs_review_count=int(
            (overrides or {}).get("needs_review_count", needs_review_count)
        ),
        dead_letter_count=int(
            (overrides or {}).get("dead_letter_count", state.metadata.get("dead_letter_count", 0))
        ),
        low_prompt_score_count=int(
            (overrides or {}).get("low_prompt_score_count", low_prompt_score_count)
        ),
        recovery_strategy_count=int(
            (overrides or {}).get("recovery_strategy_count", recovery_strategy_count)
        ),
        strategy_count=int((overrides or {}).get("strategy_count", strategy_count)),
        metadata={
            "run_id": state.run.run_id,
            "issue_id": state.run.issue_id,
            "workflow": state.run.workflow_name,
            **(overrides or {}),
        },
    )


def sync_learning_for_runtime(state: RuntimeState) -> None:
    run_id = state.run.run_id
    registry = LearningRegistry.default()
    signals = _filter_for_run(registry.list_signals(project=state.run.project), run_id)
    insights = _filter_for_run(registry.list_insights(project=state.run.project), run_id)
    recommendations = _filter_for_run(
        registry.list_recommendations(project=state.run.project),
        run_id,
    )
    state.metadata["learning_signal_ids"] = [signal.signal_id for signal in signals]
    state.metadata["learning_signals"] = [signal.model_dump(mode="json") for signal in signals]
    state.metadata["learning_signal_count"] = len(signals)
    state.metadata["insight_ids"] = [insight.insight_id for insight in insights]
    state.metadata["insights"] = [insight.model_dump(mode="json") for insight in insights]
    state.metadata["insight_count"] = len(insights)
    state.metadata["recommendation_ids"] = [
        recommendation.recommendation_id for recommendation in recommendations
    ]
    state.metadata["recommendations"] = [
        recommendation.model_dump(mode="json") for recommendation in recommendations
    ]
    state.metadata["recommendation_count"] = len(recommendations)
    latest_recommendation = recommendations[0] if recommendations else None
    max_severity = highest_severity(
        *[signal.severity for signal in signals],
        *[insight.severity for insight in insights],
    )
    state.metadata["learning_severity"] = max_severity.value if max_severity is not None else None
    state.metadata["recommendation_type"] = (
        latest_recommendation.recommendation_type.value
        if latest_recommendation is not None
        else None
    )
    sync_timeline_for_state(state)


def accept_learning_recommendation(
    recommendation_id: str,
    *,
    notes: str | None = None,
    assigned_to: str | None = None,
) -> OptimizationRecommendation:
    registry = LearningRegistry.default()
    recommendation = registry.update_recommendation_status(
        recommendation_id,
        status=RecommendationStatus.ACCEPTED,
        metadata={"decision_notes": notes, "assigned_to": assigned_to},
    )
    _complete_review_if_needed(
        recommendation,
        decision=ReviewDecision.APPROVED,
        notes=notes,
        assigned_to=assigned_to,
    )
    return registry.get_recommendation(recommendation_id) or recommendation


def reject_learning_recommendation(
    recommendation_id: str,
    *,
    notes: str | None = None,
    assigned_to: str | None = None,
) -> OptimizationRecommendation:
    registry = LearningRegistry.default()
    recommendation = registry.update_recommendation_status(
        recommendation_id,
        status=RecommendationStatus.REJECTED,
        metadata={"decision_notes": notes, "assigned_to": assigned_to},
    )
    _complete_review_if_needed(
        recommendation,
        decision=ReviewDecision.REJECTED,
        notes=notes,
        assigned_to=assigned_to,
    )
    return registry.get_recommendation(recommendation_id) or recommendation


def _filter_for_run(items: list, run_id: str) -> list:
    return [
        item
        for item in items
        if item.metadata.get("run_id") == run_id
        or item.metadata.get("source_id") == run_id
    ]


def _average_latency_ms(state: RuntimeState) -> float:
    latencies: list[float] = []
    prompt_metadata = state.metadata.get("prompt_pipeline", {})
    if isinstance(prompt_metadata, dict):
        for payload in prompt_metadata.values():
            if isinstance(payload, dict) and payload.get("latency_ms") is not None:
                latencies.append(float(payload["latency_ms"]))
    kilo_results = state.metadata.get("kilo_execution_results", {})
    if isinstance(kilo_results, dict):
        for payload in kilo_results.values():
            if not isinstance(payload, dict):
                continue
            duration_ms = payload.get("duration_ms")
            if duration_ms is not None:
                latencies.append(float(duration_ms))
    return round(mean(latencies), 2) if latencies else 0.0


def _context_values_from_overrides(overrides: dict[str, Any] | None) -> dict[str, Any]:
    allowed_keys = {
        "qa_failure_count",
        "retry_count",
        "estimated_cost_total",
        "cost_control_status",
        "avg_latency_ms",
        "needs_review_count",
        "dead_letter_count",
        "low_prompt_score_count",
        "recovery_strategy_count",
        "strategy_count",
    }
    payload = overrides or {}
    return {key: payload[key] for key in allowed_keys if key in payload}


def _create_memory_for_insights(
    state: RuntimeState,
    insights: list[OperationalInsight],
) -> None:
    created_records = []
    registry = LearningRegistry.default()
    for insight in insights:
        if insight.metadata.get("memory_id"):
            continue
        category = _memory_category_for_insight(insight)
        record = ProjectMemoryRegistry.default().add_memory(
            project=state.run.project,
            category=category,
            title=insight.title,
            content=f"{insight.description} Evidence: {'; '.join(insight.evidence)}",
            source_type=MemorySourceType.WORKFLOW,
            source_id=state.run.run_id,
            tags=["learning", insight.insight_type.value.lower(), state.run.issue_id],
            metadata={
                "run_id": state.run.run_id,
                "issue_id": state.run.issue_id,
                "insight_id": insight.insight_id,
                "insight_type": insight.insight_type.value,
                "severity": insight.severity.value,
            },
        )
        created_records.append(record)
        updated = insight.model_copy(
            update={
                "metadata": {
                    **insight.metadata,
                    "memory_id": record.memory_id,
                    "memory_category": category.value,
                }
            }
        )
        registry.save_insight(updated)
        state.metadata.setdefault("memory_record_ids", []).append(record.memory_id)
    if created_records:
        memory_metadata = build_project_memory_metadata(
            state.run.project,
            created_records=created_records,
        )
        state.metadata.update(memory_metadata)
        state.metadata["memory_records_created"] = len(state.metadata["memory_record_ids"])


def _create_reviews_for_recommendations(
    state: RuntimeState,
    recommendations: list[OptimizationRecommendation],
) -> None:
    registry = LearningRegistry.default()
    review_registry = HumanReviewRegistry.default()
    for recommendation in recommendations:
        if not recommendation.requires_human_review or recommendation.metadata.get("review_id"):
            continue
        review = review_registry.create_review(
            review_type=ReviewType.OPTIMIZATION_RECOMMENDATION,
            target_id=recommendation.recommendation_id,
            target_type="OptimizationRecommendation",
            requested_by="learning",
            assigned_to="founder",
            notes=recommendation.title,
            metadata={
                "run_id": state.run.run_id,
                "project": state.run.project,
                "issue_id": state.run.issue_id,
                "recommendation_type": recommendation.recommendation_type.value,
                "recommendation_status": recommendation.status.value,
            },
        )
        updated = recommendation.model_copy(
            update={
                "metadata": {
                    **recommendation.metadata,
                    "review_id": review.review_id,
                    "review_type": review.review_type.value,
                    "review_status": review.status.value,
                }
            }
        )
        registry.save_recommendation(updated)


def _create_memory_for_project_insights(
    *,
    project: str,
    workflow_run_id: str | None,
    issue_id: str | None,
    insights: list[OperationalInsight],
) -> None:
    registry = LearningRegistry.default()
    for insight in insights:
        if insight.metadata.get("memory_id"):
            continue
        category = _memory_category_for_insight(insight)
        record = ProjectMemoryRegistry.default().add_memory(
            project=project,
            category=category,
            title=insight.title,
            content=f"{insight.description} Evidence: {'; '.join(insight.evidence)}",
            source_type=MemorySourceType.SYSTEM,
            source_id=workflow_run_id or issue_id or "manual-analysis",
            tags=["learning", insight.insight_type.value.lower(), issue_id or project],
            metadata={
                "run_id": workflow_run_id,
                "issue_id": issue_id,
                "insight_id": insight.insight_id,
                "insight_type": insight.insight_type.value,
                "severity": insight.severity.value,
            },
        )
        registry.save_insight(
            insight.model_copy(
                update={
                    "metadata": {
                        **insight.metadata,
                        "memory_id": record.memory_id,
                        "memory_category": category.value,
                    }
                }
            )
        )


def _create_reviews_for_project_recommendations(
    *,
    project: str,
    workflow_run_id: str | None,
    issue_id: str | None,
    recommendations: list[OptimizationRecommendation],
) -> None:
    registry = LearningRegistry.default()
    review_registry = HumanReviewRegistry.default()
    for recommendation in recommendations:
        if not recommendation.requires_human_review or recommendation.metadata.get("review_id"):
            continue
        review = review_registry.create_review(
            review_type=ReviewType.OPTIMIZATION_RECOMMENDATION,
            target_id=recommendation.recommendation_id,
            target_type="OptimizationRecommendation",
            requested_by="learning",
            assigned_to="founder",
            notes=recommendation.title,
            metadata={
                "run_id": workflow_run_id,
                "project": project,
                "issue_id": issue_id,
                "recommendation_type": recommendation.recommendation_type.value,
                "recommendation_status": recommendation.status.value,
            },
        )
        registry.save_recommendation(
            recommendation.model_copy(
                update={
                    "metadata": {
                        **recommendation.metadata,
                        "review_id": review.review_id,
                        "review_type": review.review_type.value,
                        "review_status": review.status.value,
                    }
                }
            )
        )


def _complete_review_if_needed(
    recommendation: OptimizationRecommendation,
    *,
    decision: ReviewDecision,
    notes: str | None,
    assigned_to: str | None,
) -> None:
    review_id = recommendation.metadata.get("review_id")
    if not review_id:
        return
    review = HumanReviewRegistry.default().get_review(str(review_id))
    if review is None or review.status.value == "COMPLETED":
        return
    HumanReviewRegistry.default().complete_review(
        str(review_id),
        decision=decision,
        notes=notes,
        assigned_to=assigned_to,
    )


def _memory_category_for_insight(insight: OperationalInsight) -> MemoryCategory:
    if insight.insight_type.value == "PROMPT_QUALITY":
        return MemoryCategory.PROMPT_LEARNING
    if insight.insight_type.value == "QUALITY":
        return MemoryCategory.QA_ISSUE
    if insight.insight_type.value == "PLANNING_WEAKNESS":
        return MemoryCategory.TASK_LEARNING
    return MemoryCategory.IMPLEMENTATION_NOTE
