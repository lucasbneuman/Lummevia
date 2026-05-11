from lummevia_core import AgentRole

from lummevia_agents import FakeModelProvider, ModelExecutor, PromptExecutionRequest
from lummevia_agents.prompts import PromptPipeline
from lummevia_evaluations import (
    EvaluationStatus,
    PromptEvaluation,
    PromptEvaluationRegistry,
    evaluate_prompt_execution,
)


def test_fake_evaluator_passes_valid_pm_prompt_execution() -> None:
    pipeline = PromptPipeline(
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )
    result = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PM,
            project="lummevia-os",
            issue_id="LUM-EVAL-1",
            target_artifact="BusinessBrief",
            available_artifacts={
                "founder_input": {
                    "summary": "Need a controlled prompt evaluation framework."
                }
            },
            metadata={},
        )
    )

    evaluation = evaluate_prompt_execution(result)

    assert evaluation.status == EvaluationStatus.PASSED
    assert evaluation.template_id == "pm_business_brief"
    assert evaluation.template_version == "v1"
    assert evaluation.score is not None


def test_fake_evaluator_fails_when_structured_output_is_missing_expected_sections() -> None:
    evaluation = PromptEvaluationRegistry.default().evaluate(
        template_id="pm_business_brief",
        template_version="v1",
        provider="FAKE",
        model="fake:pm",
        prompt="short prompt",
        structured_output={
            "issue_id": "LUM-EVAL-2",
            "project": "lummevia-os",
            "objective": "Too incomplete",
        },
        fallback_used=True,
    )

    assert evaluation.status == EvaluationStatus.FAILED
    assert evaluation.score is not None
    assert evaluation.score < 1.0
    assert "missing_sections" in evaluation.metadata


def test_prompt_evaluation_registry_stores_results_in_memory() -> None:
    registry = PromptEvaluationRegistry.default()
    evaluation = PromptEvaluation(
        evaluation_id="eval-001",
        template_id="pm_business_brief",
        template_version="v1",
        provider="FAKE",
        model="fake:pm",
        score=0.75,
        status=EvaluationStatus.NEEDS_REVIEW,
        notes="Stored for later regression comparisons.",
        metadata={"source": "unit-test"},
    )

    registry.register(evaluation)

    assert registry.get(evaluation.evaluation_id) == evaluation
