from __future__ import annotations

from typing import ClassVar

from lummevia_learning.schemas import (
    LearningSignal,
    OperationalInsight,
    OptimizationRecommendation,
    RecommendationStatus,
)


class LearningRegistry:
    _default_instance: ClassVar["LearningRegistry" | None] = None

    def __init__(self) -> None:
        self._signals: dict[str, LearningSignal] = {}
        self._insights: dict[str, OperationalInsight] = {}
        self._recommendations: dict[str, OptimizationRecommendation] = {}

    @classmethod
    def default(cls) -> "LearningRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._signals.clear()
        self._insights.clear()
        self._recommendations.clear()

    def add_signal(self, signal: LearningSignal) -> LearningSignal:
        self._signals[signal.signal_id] = signal
        return signal

    def add_insight(self, insight: OperationalInsight) -> OperationalInsight:
        self._insights[insight.insight_id] = insight
        return insight

    def add_recommendation(
        self,
        recommendation: OptimizationRecommendation,
    ) -> OptimizationRecommendation:
        self._recommendations[recommendation.recommendation_id] = recommendation
        return recommendation

    def save_insight(self, insight: OperationalInsight) -> OperationalInsight:
        self._insights[insight.insight_id] = insight
        return insight

    def save_recommendation(
        self,
        recommendation: OptimizationRecommendation,
    ) -> OptimizationRecommendation:
        self._recommendations[recommendation.recommendation_id] = recommendation
        return recommendation

    def get_recommendation(
        self,
        recommendation_id: str,
    ) -> OptimizationRecommendation | None:
        return self._recommendations.get(recommendation_id)

    def list_signals(self, *, project: str | None = None) -> list[LearningSignal]:
        signals = list(self._signals.values())
        if project is not None:
            signals = [signal for signal in signals if signal.project == project]
        return sorted(signals, key=lambda item: (item.created_at, item.signal_id), reverse=True)

    def list_insights(self, *, project: str | None = None) -> list[OperationalInsight]:
        insights = list(self._insights.values())
        if project is not None:
            insights = [insight for insight in insights if insight.project == project]
        return sorted(insights, key=lambda item: (item.created_at, item.insight_id), reverse=True)

    def list_recommendations(
        self,
        *,
        project: str | None = None,
    ) -> list[OptimizationRecommendation]:
        recommendations = list(self._recommendations.values())
        if project is not None:
            recommendations = [
                recommendation
                for recommendation in recommendations
                if recommendation.project == project
            ]
        return sorted(
            recommendations,
            key=lambda item: (item.created_at, item.recommendation_id),
            reverse=True,
        )

    def update_recommendation_status(
        self,
        recommendation_id: str,
        *,
        status: RecommendationStatus,
        metadata: dict | None = None,
    ) -> OptimizationRecommendation:
        recommendation = self._recommendations[recommendation_id]
        updated = recommendation.model_copy(
            update={
                "status": status,
                "metadata": {
                    **recommendation.metadata,
                    **(metadata or {}),
                },
            }
        )
        self._recommendations[recommendation_id] = updated
        return updated
