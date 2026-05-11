from __future__ import annotations

from datetime import UTC, datetime

from lummevia_evaluations import (
    PromptBaselineRegistry,
    PromotionStatus,
    RegressionRunResult,
    RegressionRunSummary,
)


def build_regression_run(
    *,
    template_id: str,
    template_version: str,
    passed: int,
    failed: int,
    avg_score: float,
    avg_latency_ms: float,
) -> RegressionRunResult:
    now = datetime.now(UTC)
    return RegressionRunResult(
        regression_run_id=f"regr-{template_version}",
        template_id=template_id,
        template_version=template_version,
        dataset_id="pm_business_brief_dataset",
        summary=RegressionRunSummary(
            total=passed + failed,
            passed=passed,
            failed=failed,
            avg_score=avg_score,
            avg_latency_ms=avg_latency_ms,
        ),
        cases=[],
        started_at=now,
        completed_at=now,
    )


def test_baseline_registry_promotes_first_candidate_without_previous_baseline() -> None:
    registry = PromptBaselineRegistry()
    candidate_run = build_regression_run(
        template_id="pm_business_brief",
        template_version="v1",
        passed=5,
        failed=0,
        avg_score=0.91,
        avg_latency_ms=120.0,
    )

    result = registry.promote(
        template_id="pm_business_brief",
        candidate_version="v1",
        regression_run=candidate_run,
        promoted_by="pm",
        notes="initial baseline",
    )

    assert result.previous_version is None
    assert result.promotion_status is PromotionStatus.PROMOTED
    assert registry.get_active_version("pm_business_brief") == "v1"


def test_baseline_registry_promotes_candidate_that_improves_baseline() -> None:
    registry = PromptBaselineRegistry()
    baseline_run = build_regression_run(
        template_id="pm_business_brief",
        template_version="v1",
        passed=4,
        failed=1,
        avg_score=0.72,
        avg_latency_ms=150.0,
    )
    registry.promote(
        template_id="pm_business_brief",
        candidate_version="v1",
        regression_run=baseline_run,
    )
    improved_run = build_regression_run(
        template_id="pm_business_brief",
        template_version="v2",
        passed=5,
        failed=0,
        avg_score=0.93,
        avg_latency_ms=140.0,
    )

    comparison = registry.compare(
        template_id="pm_business_brief",
        candidate_version="v2",
        current_summary=improved_run.summary,
    )
    result = registry.promote(
        template_id="pm_business_brief",
        candidate_version="v2",
        regression_run=improved_run,
        comparison=comparison,
    )

    assert comparison.delta_score is not None and comparison.delta_score > 0
    assert result.previous_version == "v1"
    assert result.promotion_status is PromotionStatus.PROMOTED
    assert registry.get_active_version("pm_business_brief") == "v2"


def test_baseline_registry_rejects_bad_regression() -> None:
    registry = PromptBaselineRegistry()
    baseline_run = build_regression_run(
        template_id="pm_business_brief",
        template_version="v1",
        passed=5,
        failed=0,
        avg_score=0.94,
        avg_latency_ms=100.0,
    )
    registry.promote(
        template_id="pm_business_brief",
        candidate_version="v1",
        regression_run=baseline_run,
    )
    regressed_run = build_regression_run(
        template_id="pm_business_brief",
        template_version="v2",
        passed=2,
        failed=3,
        avg_score=0.7,
        avg_latency_ms=180.0,
    )

    comparison = registry.compare(
        template_id="pm_business_brief",
        candidate_version="v2",
        current_summary=regressed_run.summary,
    )
    result = registry.promote(
        template_id="pm_business_brief",
        candidate_version="v2",
        regression_run=regressed_run,
        comparison=comparison,
    )

    assert result.promotion_status is PromotionStatus.REJECTED
    assert result.regression_passed is False
    assert registry.get_active_version("pm_business_brief") == "v1"
