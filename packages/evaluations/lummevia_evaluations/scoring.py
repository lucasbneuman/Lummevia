from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

from lummevia_evaluations.schemas import EvaluationStatus, PromptEvaluation


DEFAULT_MIN_PROMPT_LENGTH = 120
DEFAULT_EXPECTED_SECTIONS: dict[str, tuple[str, ...]] = {
    "pm_business_brief": (
        "objective",
        "problem",
        "expected_impact",
        "constraints",
        "kpis",
    ),
    "po_execution_package": (
        "technical_story",
        "acceptance_criteria",
        "edge_cases",
        "testing_scenarios",
    ),
    "po_task_plan": (
        "workstreams",
        "task_packages",
        "sequencing_notes",
        "risks",
    ),
    "po_task_package": (
        "task_id",
        "title",
        "objective",
        "acceptance_criteria",
    ),
    "dev_implementation_package": (
        "branch",
        "commits",
        "files_changed",
        "summary",
    ),
    "qa_validation_package": (
        "status",
        "scenarios_validated",
        "feedback",
    ),
    "qc_quality_approval": (
        "status",
        "architecture_ok",
        "standards_ok",
        "observations",
    ),
}


def build_evaluation_id(
    *,
    template_id: str,
    template_version: str,
    provider: str,
    model: str,
    prompt: str,
) -> str:
    digest = sha256(
        "|".join(
            [
                template_id,
                template_version,
                provider,
                model,
                prompt,
            ]
        ).encode("utf-8")
    ).hexdigest()
    return f"eval-{digest[:12]}"


def score_prompt_execution(
    *,
    template_id: str,
    template_version: str,
    provider: str,
    model: str,
    prompt: str,
    structured_output: Any,
    fallback_used: bool,
    expected_sections: Sequence[str] | None = None,
    min_prompt_length: int = DEFAULT_MIN_PROMPT_LENGTH,
) -> PromptEvaluation:
    output_payload = _normalize_structured_output(structured_output)
    prompt_length = len(prompt.strip())
    structured_output_valid = bool(output_payload)
    required_sections = tuple(
        expected_sections if expected_sections is not None else DEFAULT_EXPECTED_SECTIONS.get(template_id, ())
    )
    missing_sections = [
        section
        for section in required_sections
        if not _has_meaningful_value(output_payload.get(section))
    ]

    score = 1.0
    notes: list[str] = []

    if prompt_length < min_prompt_length:
        score -= 0.35
        notes.append("prompt_too_short")
    if not structured_output_valid:
        score -= 0.45
        notes.append("structured_output_invalid")
    if missing_sections:
        score -= 0.35
        notes.append("missing_expected_sections")
    if fallback_used:
        score -= 0.1
        notes.append("fallback_used")

    score = max(0.0, round(score, 4))

    status = EvaluationStatus.PASSED
    if not structured_output_valid or missing_sections:
        status = EvaluationStatus.FAILED
    elif prompt_length < min_prompt_length and score < 0.7:
        status = EvaluationStatus.FAILED
    elif score < 0.7:
        status = EvaluationStatus.NEEDS_REVIEW

    return PromptEvaluation(
        evaluation_id=build_evaluation_id(
            template_id=template_id,
            template_version=template_version,
            provider=provider,
            model=model,
            prompt=prompt,
        ),
        template_id=template_id,
        template_version=template_version,
        provider=provider,
        model=model,
        score=score,
        status=status,
        notes=", ".join(notes) if notes else "Fake evaluator checks passed.",
        metadata={
            "prompt_length": prompt_length,
            "min_prompt_length": min_prompt_length,
            "structured_output_valid": structured_output_valid,
            "expected_sections": list(required_sections),
            "missing_sections": missing_sections,
            "fallback_used": fallback_used,
        },
    )


def _normalize_structured_output(structured_output: Any) -> dict[str, Any]:
    if structured_output is None:
        return {}
    if hasattr(structured_output, "model_dump"):
        dumped = structured_output.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    if isinstance(structured_output, Mapping):
        return dict(structured_output)
    return {}


def _has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return len(value) > 0
    return True
