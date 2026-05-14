from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lummevia_learning.policies import (
    FREQUENT_RECOVERY_MIN_COUNT,
    FREQUENT_RECOVERY_RATIO,
    HIGH_COST_THRESHOLD,
    HIGH_LATENCY_THRESHOLD_MS,
    HIGH_RETRY_THRESHOLD,
    LOW_PROMPT_SCORE_THRESHOLD,
    MANY_NEEDS_REVIEW_THRESHOLD,
    REPEATED_QA_FAILURE_THRESHOLD,
)
from lummevia_learning.schemas import (
    InsightType,
    LearningSeverity,
    LearningSignal,
    OperationalInsight,
    SignalType,
)


class LearningAnalysisContext(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project: str = Field(min_length=1)
    source_type: str = "RUNTIME"
    source_id: str = "manual-analysis"
    qa_failure_count: int = Field(default=0, ge=0)
    retry_count: int = Field(default=0, ge=0)
    estimated_cost_total: float = Field(default=0.0, ge=0.0)
    cost_control_status: str = Field(default="ALLOW", min_length=1)
    avg_latency_ms: float = Field(default=0.0, ge=0.0)
    needs_review_count: int = Field(default=0, ge=0)
    dead_letter_count: int = Field(default=0, ge=0)
    low_prompt_score_count: int = Field(default=0, ge=0)
    recovery_strategy_count: int = Field(default=0, ge=0)
    strategy_count: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningAnalyzer:
    def analyze(
        self,
        context: LearningAnalysisContext,
    ) -> tuple[list[LearningSignal], list[OperationalInsight]]:
        signals: list[LearningSignal] = []
        insights: list[OperationalInsight] = []

        if context.qa_failure_count >= REPEATED_QA_FAILURE_THRESHOLD:
            signal = self._signal(
                context,
                signal_type=SignalType.QA_FAILURES_REPEATED,
                severity=LearningSeverity.HIGH,
                confidence=0.9,
                summary=(
                    f"Detected {context.qa_failure_count} QA failures for project "
                    f"'{context.project}'."
                ),
                metadata={"qa_failure_count": context.qa_failure_count},
            )
            signals.append(signal)
            insights.append(
                self._insight(
                    context,
                    insight_type=InsightType.QUALITY,
                    severity=signal.severity,
                    confidence=signal.confidence,
                    title="Repeated QA failures point to a quality problem",
                    description=(
                        "The workflow is failing QA repeatedly, which suggests weak "
                        "acceptance coverage or incomplete implementation passes."
                    ),
                    evidence=[signal.summary],
                    metadata={"signal_ids": [signal.signal_id]},
                )
            )

        if context.retry_count >= HIGH_RETRY_THRESHOLD:
            signal = self._signal(
                context,
                signal_type=SignalType.HIGH_RETRY_RATE,
                severity=LearningSeverity.MEDIUM,
                confidence=0.85,
                summary=f"Detected retry_count={context.retry_count}.",
                metadata={"retry_count": context.retry_count},
            )
            signals.append(signal)
            insights.append(
                self._insight(
                    context,
                    insight_type=InsightType.EXECUTION_INSTABILITY,
                    severity=signal.severity,
                    confidence=signal.confidence,
                    title="High retries indicate unstable execution",
                    description=(
                        "The runtime is needing multiple retries, which often means the "
                        "execution path is brittle or under-specified."
                    ),
                    evidence=[signal.summary],
                    metadata={"signal_ids": [signal.signal_id]},
                )
            )

        cost_status = context.cost_control_status.upper()
        if context.estimated_cost_total >= HIGH_COST_THRESHOLD or cost_status in {"WARN", "DEGRADE", "BLOCK"}:
            severity = LearningSeverity.MEDIUM
            if cost_status == "DEGRADE":
                severity = LearningSeverity.HIGH
            if cost_status == "BLOCK":
                severity = LearningSeverity.CRITICAL
            signal = self._signal(
                context,
                signal_type=SignalType.HIGH_COST,
                severity=severity,
                confidence=0.88,
                summary=(
                    f"Estimated cost reached {context.estimated_cost_total:.4f} with "
                    f"cost status '{cost_status}'."
                ),
                metadata={
                    "estimated_cost_total": context.estimated_cost_total,
                    "cost_control_status": cost_status,
                },
            )
            signals.append(signal)
            insights.append(
                self._insight(
                    context,
                    insight_type=InsightType.ECONOMIC,
                    severity=signal.severity,
                    confidence=signal.confidence,
                    title="Execution cost is trending high",
                    description=(
                        "The current workflow is consuming more budget than expected and "
                        "should be reviewed for cheaper execution paths."
                    ),
                    evidence=[signal.summary],
                    metadata={"signal_ids": [signal.signal_id]},
                )
            )

        if context.avg_latency_ms >= HIGH_LATENCY_THRESHOLD_MS:
            signal = self._signal(
                context,
                signal_type=SignalType.HIGH_LATENCY,
                severity=LearningSeverity.MEDIUM,
                confidence=0.82,
                summary=f"Average latency reached {context.avg_latency_ms:.2f} ms.",
                metadata={"avg_latency_ms": context.avg_latency_ms},
            )
            signals.append(signal)
            insights.append(
                self._insight(
                    context,
                    insight_type=InsightType.PERFORMANCE,
                    severity=signal.severity,
                    confidence=signal.confidence,
                    title="High latency is slowing workflow execution",
                    description=(
                        "Observed latency is high enough to justify performance-oriented "
                        "workflow tuning."
                    ),
                    evidence=[signal.summary],
                    metadata={"signal_ids": [signal.signal_id]},
                )
            )

        if context.needs_review_count >= MANY_NEEDS_REVIEW_THRESHOLD:
            signal = self._signal(
                context,
                signal_type=SignalType.MANY_NEEDS_REVIEW,
                severity=LearningSeverity.MEDIUM,
                confidence=0.8,
                summary=f"Detected {context.needs_review_count} review-gated outcomes.",
                metadata={"needs_review_count": context.needs_review_count},
            )
            signals.append(signal)
            insights.append(
                self._insight(
                    context,
                    insight_type=InsightType.GOVERNANCE,
                    severity=signal.severity,
                    confidence=signal.confidence,
                    title="Review pressure is increasing governance load",
                    description=(
                        "Many review-gated outcomes suggest the workflow needs clearer "
                        "guardrails before work reaches human approval."
                    ),
                    evidence=[signal.summary],
                    metadata={"signal_ids": [signal.signal_id]},
                )
            )

        if context.dead_letter_count > 0:
            severity = (
                LearningSeverity.CRITICAL if context.dead_letter_count > 1 else LearningSeverity.HIGH
            )
            signal = self._signal(
                context,
                signal_type=SignalType.DEAD_LETTERS,
                severity=severity,
                confidence=0.95,
                summary=f"Detected {context.dead_letter_count} dead-lettered executions.",
                metadata={"dead_letter_count": context.dead_letter_count},
            )
            signals.append(signal)
            insights.append(
                self._insight(
                    context,
                    insight_type=InsightType.RESILIENCE,
                    severity=signal.severity,
                    confidence=signal.confidence,
                    title="Dead letters reveal resilience issues",
                    description=(
                        "Executions are exhausting recovery capacity and falling into "
                        "dead-letter handling."
                    ),
                    evidence=[signal.summary],
                    metadata={"signal_ids": [signal.signal_id]},
                )
            )

        if context.low_prompt_score_count > 0:
            signal = self._signal(
                context,
                signal_type=SignalType.LOW_PROMPT_SCORE,
                severity=LearningSeverity.MEDIUM,
                confidence=0.86,
                summary=(
                    f"Detected {context.low_prompt_score_count} prompt evaluations below "
                    f"{LOW_PROMPT_SCORE_THRESHOLD:.2f} or requiring review."
                ),
                metadata={"low_prompt_score_count": context.low_prompt_score_count},
            )
            signals.append(signal)
            insights.append(
                self._insight(
                    context,
                    insight_type=InsightType.PROMPT_QUALITY,
                    severity=signal.severity,
                    confidence=signal.confidence,
                    title="Prompt quality is underperforming",
                    description=(
                        "Prompt evaluations indicate that one or more templates are below "
                        "the expected quality bar."
                    ),
                    evidence=[signal.summary],
                    metadata={"signal_ids": [signal.signal_id]},
                )
            )

        recovery_ratio = (
            float(context.recovery_strategy_count) / float(context.strategy_count)
            if context.strategy_count > 0
            else 0.0
        )
        if (
            context.recovery_strategy_count >= FREQUENT_RECOVERY_MIN_COUNT
            and recovery_ratio >= FREQUENT_RECOVERY_RATIO
        ):
            signal = self._signal(
                context,
                signal_type=SignalType.FREQUENT_RECOVERY_STRATEGY,
                severity=LearningSeverity.MEDIUM,
                confidence=0.84,
                summary=(
                    f"Recovery strategy was selected {context.recovery_strategy_count} "
                    f"times out of {context.strategy_count}."
                ),
                metadata={
                    "recovery_strategy_count": context.recovery_strategy_count,
                    "strategy_count": context.strategy_count,
                    "recovery_ratio": round(recovery_ratio, 4),
                },
            )
            signals.append(signal)
            insights.append(
                self._insight(
                    context,
                    insight_type=InsightType.PLANNING_WEAKNESS,
                    severity=signal.severity,
                    confidence=signal.confidence,
                    title="Frequent recovery strategy suggests weak planning",
                    description=(
                        "The system is relying on recovery mode too often, which points to "
                        "task sizing or strategy issues upstream."
                    ),
                    evidence=[signal.summary],
                    metadata={"signal_ids": [signal.signal_id]},
                )
            )

        return signals, insights

    def _signal(
        self,
        context: LearningAnalysisContext,
        *,
        signal_type: SignalType,
        severity: LearningSeverity,
        confidence: float,
        summary: str,
        metadata: dict[str, Any],
    ) -> LearningSignal:
        return LearningSignal(
            project=context.project,
            source_type=context.source_type,
            source_id=context.source_id,
            signal_type=signal_type,
            severity=severity,
            confidence=confidence,
            summary=summary,
            metadata={
                **context.metadata,
                **metadata,
            },
        )

    def _insight(
        self,
        context: LearningAnalysisContext,
        *,
        insight_type: InsightType,
        severity: LearningSeverity,
        confidence: float,
        title: str,
        description: str,
        evidence: list[str],
        metadata: dict[str, Any],
    ) -> OperationalInsight:
        return OperationalInsight(
            project=context.project,
            insight_type=insight_type,
            severity=severity,
            confidence=confidence,
            title=title,
            description=description,
            evidence=evidence,
            metadata={
                **context.metadata,
                "source_type": context.source_type,
                "source_id": context.source_id,
                **metadata,
            },
        )
