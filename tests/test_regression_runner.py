from __future__ import annotations

from model_router import RoutingResolution

from lummevia_agents import (
    FakeModelProvider,
    ModelExecutionRequest,
    ModelExecutor,
    PromptPipeline,
)
from lummevia_agents.execution import ProviderExecutionPayload
from lummevia_datasets import get_dataset
from lummevia_evaluations import EvaluationStatus
from lummevia_evaluations.regression import PromptRegressionRunner


class PartialFailureProvider:
    def execute(
        self,
        request: ModelExecutionRequest,
        resolution: RoutingResolution,
    ) -> ProviderExecutionPayload:
        if request.metadata.get("regression_case_id") == "pm-retention-001":
            raise RuntimeError("Synthetic regression provider failure.")

        return FakeModelProvider().execute(request, resolution)


def test_regression_runner_executes_dataset_cases() -> None:
    dataset = get_dataset("pm_business_brief_dataset")
    runner = PromptRegressionRunner(
        pipeline=PromptPipeline(
            model_executor=ModelExecutor(provider=FakeModelProvider()),
        )
    )

    result = runner.run_dataset(dataset, project="lummevia-os")

    assert result.dataset_id == dataset.dataset_id
    assert result.template_id == dataset.template_id
    assert result.template_version == "v1"
    assert result.summary.total == len(dataset.cases)
    assert result.summary.passed == len(dataset.cases)
    assert result.summary.failed == 0
    assert result.summary.avg_score > 0
    assert result.summary.avg_latency_ms >= 0
    assert all(case.passed for case in result.cases)
    assert all(case.evaluation_status == EvaluationStatus.PASSED for case in result.cases)


def test_regression_runner_summary_reflects_partial_failures() -> None:
    dataset = get_dataset("pm_business_brief_dataset")
    runner = PromptRegressionRunner(
        pipeline=PromptPipeline(
            model_executor=ModelExecutor(provider=PartialFailureProvider()),
        )
    )

    result = runner.run_dataset(dataset, project="lummevia-os")

    assert result.summary.total == len(dataset.cases)
    assert result.summary.passed == len(dataset.cases) - 1
    assert result.summary.failed == 1
    assert result.summary.avg_score < 1.0
    failed_case = next(case for case in result.cases if not case.passed)
    assert failed_case.case_id == "pm-retention-001"
    assert failed_case.evaluation_status == EvaluationStatus.FAILED
    assert failed_case.error == "Synthetic regression provider failure."
