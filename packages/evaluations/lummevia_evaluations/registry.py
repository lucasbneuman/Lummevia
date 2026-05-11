from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from lummevia_evaluations.scoring import (
    DEFAULT_EXPECTED_SECTIONS,
    score_prompt_execution,
)
from lummevia_evaluations.schemas import PromptEvaluation


class PromptEvaluationRegistry:
    _default_instance: ClassVar["PromptEvaluationRegistry" | None] = None

    def __init__(
        self,
        *,
        expected_sections_by_template: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self._expected_sections_by_template = (
            expected_sections_by_template or dict(DEFAULT_EXPECTED_SECTIONS)
        )
        self._evaluations: dict[str, PromptEvaluation] = {}

    @classmethod
    def default(cls) -> "PromptEvaluationRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def register(self, evaluation: PromptEvaluation) -> PromptEvaluation:
        self._evaluations[evaluation.evaluation_id] = evaluation
        return evaluation

    def get(self, evaluation_id: str) -> PromptEvaluation | None:
        return self._evaluations.get(evaluation_id)

    def evaluate(
        self,
        *,
        template_id: str,
        template_version: str,
        provider: str,
        model: str,
        prompt: str,
        structured_output: Any,
        fallback_used: bool,
    ) -> PromptEvaluation:
        evaluation = score_prompt_execution(
            template_id=template_id,
            template_version=template_version,
            provider=provider,
            model=model,
            prompt=prompt,
            structured_output=structured_output,
            fallback_used=fallback_used,
            expected_sections=self._expected_sections_by_template.get(template_id),
        )
        return self.register(evaluation)

    def expected_sections(self, template_id: str) -> Sequence[str]:
        return self._expected_sections_by_template.get(template_id, ())
