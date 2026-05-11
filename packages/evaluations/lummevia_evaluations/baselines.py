from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

from lummevia_evaluations.schemas import (
    PromptBaseline,
    PromptPromotionResult,
    PromotionStatus,
    RegressionRunResult,
    RegressionRunSummary,
)

MAX_FAILED_CASES_INCREASE_REJECT = 2
MAX_FAILED_CASES_INCREASE_REVIEW = 1
MAX_SCORE_DROP_REJECT = 0.1
MAX_SCORE_DROP_REVIEW = 0.03
MAX_LATENCY_INCREASE_REVIEW_MS = 250.0
MAX_PASS_RATE_DROP_REJECT = 0.2


@dataclass(slots=True)
class BaselineComparison:
    baseline_version: str | None
    candidate_version: str
    promotion_status: PromotionStatus
    regression_passed: bool
    summary: str
    delta_score: float | None
    delta_pass_rate: float | None
    delta_latency_ms: float | None
    failed_cases_delta: int | None


class PromptBaselineRegistry:
    _default_instance: ClassVar["PromptBaselineRegistry" | None] = None

    def __init__(self) -> None:
        self._baselines: dict[str, PromptBaseline] = {}

    @classmethod
    def default(cls) -> "PromptBaselineRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._baselines.clear()

    def register(self, baseline: PromptBaseline) -> PromptBaseline:
        self._baselines[baseline.template_id] = baseline
        return baseline

    def get(self, template_id: str) -> PromptBaseline | None:
        return self._baselines.get(template_id)

    def get_active_version(self, template_id: str) -> str | None:
        baseline = self.get(template_id)
        return baseline.active_version if baseline is not None else None

    def compare(
        self,
        *,
        template_id: str,
        candidate_version: str,
        current_summary: RegressionRunSummary,
    ) -> BaselineComparison:
        baseline = self.get(template_id)
        if baseline is None:
            return BaselineComparison(
                baseline_version=None,
                candidate_version=candidate_version,
                promotion_status=PromotionStatus.PROMOTED,
                regression_passed=True,
                summary=(
                    "No previous baseline was registered. "
                    "Candidate promoted as the first active baseline."
                ),
                delta_score=None,
                delta_pass_rate=None,
                delta_latency_ms=None,
                failed_cases_delta=None,
            )

        baseline_summary = baseline.regression_summary
        baseline_pass_rate = self._pass_rate(baseline_summary)
        current_pass_rate = self._pass_rate(current_summary)
        delta_score = round(current_summary.avg_score - baseline_summary.avg_score, 4)
        delta_pass_rate = round(current_pass_rate - baseline_pass_rate, 4)
        delta_latency_ms = round(
            current_summary.avg_latency_ms - baseline_summary.avg_latency_ms,
            2,
        )
        failed_cases_delta = current_summary.failed - baseline_summary.failed

        status = PromotionStatus.PROMOTED
        regression_passed = True
        summary = "Candidate matched or improved the active baseline."

        if (
            failed_cases_delta >= MAX_FAILED_CASES_INCREASE_REJECT
            or delta_pass_rate <= -MAX_PASS_RATE_DROP_REJECT
            or delta_score <= -MAX_SCORE_DROP_REJECT
        ):
            status = PromotionStatus.REJECTED
            regression_passed = False
            summary = (
                "Candidate regressed too far from the active baseline and was rejected."
            )
        elif (
            failed_cases_delta >= MAX_FAILED_CASES_INCREASE_REVIEW
            or delta_score <= -MAX_SCORE_DROP_REVIEW
            or delta_latency_ms > MAX_LATENCY_INCREASE_REVIEW_MS
        ):
            status = PromotionStatus.NEEDS_REVIEW
            regression_passed = True
            summary = (
                "Candidate is close to the active baseline but requires manual review."
            )

        return BaselineComparison(
            baseline_version=baseline.active_version,
            candidate_version=candidate_version,
            promotion_status=status,
            regression_passed=regression_passed,
            summary=summary,
            delta_score=delta_score,
            delta_pass_rate=delta_pass_rate,
            delta_latency_ms=delta_latency_ms,
            failed_cases_delta=failed_cases_delta,
        )

    def promote(
        self,
        *,
        template_id: str,
        candidate_version: str,
        regression_run: RegressionRunResult,
        promoted_by: str | None = None,
        notes: str | None = None,
        metadata: dict[str, Any] | None = None,
        comparison: BaselineComparison | None = None,
    ) -> PromptPromotionResult:
        comparison = comparison or self.compare(
            template_id=template_id,
            candidate_version=candidate_version,
            current_summary=regression_run.summary,
        )
        timestamp = datetime.now(UTC)

        if comparison.promotion_status is PromotionStatus.PROMOTED:
            self.register(
                PromptBaseline(
                    template_id=template_id,
                    active_version=candidate_version,
                    promoted_at=timestamp,
                    promoted_by=promoted_by,
                    regression_summary=regression_run.summary,
                    notes=notes,
                    metadata=metadata or {},
                )
            )

        return PromptPromotionResult(
            template_id=template_id,
            previous_version=comparison.baseline_version,
            promoted_version=candidate_version,
            promotion_status=comparison.promotion_status,
            regression_passed=comparison.regression_passed,
            summary=comparison.summary,
            timestamp=timestamp,
        )

    def _pass_rate(self, summary: RegressionRunSummary) -> float:
        if summary.total == 0:
            return 0.0
        return summary.passed / summary.total
