from __future__ import annotations

from typing import Any

from lummevia_learning.schemas import (
    InsightType,
    OperationalInsight,
    OptimizationRecommendation,
    RecommendationType,
)


def generate_recommendations(
    *,
    project: str,
    insights: list[OperationalInsight],
    metadata: dict[str, Any] | None = None,
) -> list[OptimizationRecommendation]:
    recommendations: list[OptimizationRecommendation] = []
    shared_metadata = metadata or {}

    for insight in insights:
        recommendation_payloads = _recommendation_payloads_for_insight(insight)
        for payload in recommendation_payloads:
            recommendations.append(
                OptimizationRecommendation(
                    project=project,
                    recommendation_type=payload["recommendation_type"],
                    confidence=min(0.99, round(insight.confidence - 0.02, 2)),
                    title=payload["title"],
                    description=payload["description"],
                    expected_impact=payload["expected_impact"],
                    requires_human_review=True,
                    metadata={
                        **shared_metadata,
                        "insight_id": insight.insight_id,
                        "insight_type": insight.insight_type.value,
                        "severity": insight.severity.value,
                    },
                )
            )
    return recommendations


def _recommendation_payloads_for_insight(
    insight: OperationalInsight,
) -> list[dict[str, Any]]:
    if insight.insight_type == InsightType.QUALITY:
        return [
            {
                "recommendation_type": RecommendationType.STRICTER_QA,
                "title": "Raise QA strictness for similar tasks",
                "description": "Increase QA depth before closing similar TaskPackages.",
                "expected_impact": "Reduce repeat QA failures before PR stage.",
            },
            {
                "recommendation_type": RecommendationType.SPLIT_TASK_PACKAGE,
                "title": "Split oversized TaskPackages",
                "description": "Break large execution units into smaller verifiable slices.",
                "expected_impact": "Improve acceptance clarity and reduce defect density.",
            },
        ]
    if insight.insight_type == InsightType.EXECUTION_INSTABILITY:
        return [
            {
                "recommendation_type": RecommendationType.LOWER_AUTONOMY,
                "title": "Lower autonomy on unstable paths",
                "description": "Use a more conservative execution mode when retries spike.",
                "expected_impact": "Reduce churn and limit unstable retries.",
            },
            {
                "recommendation_type": RecommendationType.CREATE_REVIEW_GATE,
                "title": "Add a review gate before unstable execution repeats",
                "description": "Insert a human review checkpoint earlier in the workflow.",
                "expected_impact": "Catch instability before it compounds downstream.",
            },
        ]
    if insight.insight_type == InsightType.ECONOMIC:
        return [
            {
                "recommendation_type": RecommendationType.USE_MODEL_LITE,
                "title": "Evaluate a lighter model profile",
                "description": "Propose a lower-cost model tier for suitable steps.",
                "expected_impact": "Reduce estimated cost without changing policies automatically.",
            }
        ]
    if insight.insight_type == InsightType.PERFORMANCE:
        return [
            {
                "recommendation_type": RecommendationType.SPLIT_TASK_PACKAGE,
                "title": "Reduce latency by shrinking execution scope",
                "description": "Break slow units into smaller packages with tighter context.",
                "expected_impact": "Lower per-step latency and improve throughput.",
            }
        ]
    if insight.insight_type == InsightType.GOVERNANCE:
        return [
            {
                "recommendation_type": RecommendationType.CREATE_REVIEW_GATE,
                "title": "Formalize a review gate",
                "description": "Add an explicit human gate where review pressure is recurring.",
                "expected_impact": "Improve governance visibility and reduce ambiguous approvals.",
            }
        ]
    if insight.insight_type == InsightType.RESILIENCE:
        return [
            {
                "recommendation_type": RecommendationType.REVIEW_STRATEGY,
                "title": "Review recovery and execution strategy",
                "description": "Inspect recovery thresholds and path selection for resilience issues.",
                "expected_impact": "Reduce dead letters and improve recoverability.",
            }
        ]
    if insight.insight_type == InsightType.PROMPT_QUALITY:
        return [
            {
                "recommendation_type": RecommendationType.IMPROVE_PROMPT,
                "title": "Review prompt design",
                "description": "Revise prompt structure manually based on low evaluation signals.",
                "expected_impact": "Improve prompt scores without auto-changing templates.",
            },
            {
                "recommendation_type": RecommendationType.ADD_MEMORY_CONTEXT,
                "title": "Add project memory context",
                "description": "Feed relevant memory records into prompt preparation where helpful.",
                "expected_impact": "Increase prompt relevance and reduce avoidable review churn.",
            },
        ]
    if insight.insight_type == InsightType.PLANNING_WEAKNESS:
        return [
            {
                "recommendation_type": RecommendationType.REVIEW_STRATEGY,
                "title": "Review execution strategy selection",
                "description": "Inspect why RECOVERY is being selected so often.",
                "expected_impact": "Strengthen upstream planning and reduce recovery dependence.",
            },
            {
                "recommendation_type": RecommendationType.SPLIT_TASK_PACKAGE,
                "title": "Refine TaskPackage planning",
                "description": "Decompose work earlier when planning repeatedly falls back to recovery.",
                "expected_impact": "Improve plan quality before execution begins.",
            },
        ]
    return []
