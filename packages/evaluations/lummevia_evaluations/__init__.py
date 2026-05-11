from lummevia_evaluations.registry import PromptEvaluationRegistry
from lummevia_evaluations.schemas import EvaluationStatus, PromptEvaluation


def evaluate_prompt_execution(
    prompt_execution_result,
    *,
    registry: PromptEvaluationRegistry | None = None,
) -> PromptEvaluation:
    evaluation_registry = registry or PromptEvaluationRegistry.default()
    return evaluation_registry.evaluate(
        template_id=prompt_execution_result.template_id,
        template_version=prompt_execution_result.template_version,
        provider=prompt_execution_result.model_execution.provider,
        model=prompt_execution_result.model_execution.model,
        prompt=prompt_execution_result.prompt,
        structured_output=prompt_execution_result.structured_output,
        fallback_used=prompt_execution_result.model_execution.fallback_used,
    )


__all__ = [
    "EvaluationStatus",
    "PromptEvaluation",
    "PromptEvaluationRegistry",
    "evaluate_prompt_execution",
]
