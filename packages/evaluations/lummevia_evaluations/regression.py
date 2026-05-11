from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from lummevia_agents.execution import ModelExecutionError
from lummevia_agents.prompts.pipeline import PromptExecutionRequest, PromptPipeline
from lummevia_core import AgentRole
from lummevia_datasets import PromptDataset, PromptDatasetCase
from lummevia_evaluations.schemas import (
    EvaluationStatus,
    RegressionCaseResult,
    RegressionRunResult,
    RegressionRunSummary,
)
from lummevia_evaluations.scoring import score_prompt_execution


class PromptRegressionRunner:
    def __init__(self, *, pipeline: PromptPipeline | None = None) -> None:
        self.pipeline = pipeline or PromptPipeline()

    def run_dataset(
        self,
        dataset: PromptDataset,
        *,
        project: str,
        template_version: str | None = None,
    ) -> RegressionRunResult:
        template = self.pipeline.registry.get_template_by_id(
            dataset.template_id,
            version=template_version,
        )
        regression_run_id = f"regr-{uuid4().hex[:12]}"
        started_at = datetime.now(UTC)
        cases = [
            self._run_case(
                dataset=dataset,
                case=case,
                project=project,
                template=template,
            )
            for case in dataset.cases
        ]
        completed_at = datetime.now(UTC)

        summary = self._build_summary(cases)
        return RegressionRunResult(
            regression_run_id=regression_run_id,
            template_id=dataset.template_id,
            template_version=template.version,
            dataset_id=dataset.dataset_id,
            summary=summary,
            cases=cases,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _run_case(
        self,
        *,
        dataset: PromptDataset,
        case: PromptDatasetCase,
        project: str,
        template,
    ) -> RegressionCaseResult:
        request = PromptExecutionRequest(
            role=template.role,
            project=project,
            issue_id=str(case.metadata.get("issue_id", case.case_id)),
            target_artifact=template.target_artifact,
            template_version=template.version,
            available_artifacts=self._build_available_artifacts(
                template_id=dataset.template_id,
                case=case,
            ),
            metadata={
                **case.metadata,
                "regression_case_id": case.case_id,
                "regression_dataset_id": dataset.dataset_id,
            },
        )

        try:
            result = self.pipeline.execute(request)
        except ModelExecutionError as exc:
            return RegressionCaseResult(
                case_id=case.case_id,
                dataset_id=dataset.dataset_id,
                template_id=dataset.template_id,
                template_version=template.version,
                input_prompt=case.input_prompt,
                expected_keywords=list(case.expected_keywords),
                expected_sections=list(case.expected_sections),
                missing_keywords=list(case.expected_keywords),
                missing_sections=list(case.expected_sections),
                passed=False,
                score=0.0,
                latency_ms=0,
                fallback_used=False,
                evaluation_status=EvaluationStatus.FAILED,
                error=str(exc.__cause__ or exc),
                metadata={
                    "project": project,
                    "issue_id": request.issue_id,
                },
            )

        structured_output = result.structured_output.model_dump(mode="json")
        evaluation = score_prompt_execution(
            template_id=result.template_id,
            template_version=result.template_version,
            provider=result.model_execution.provider,
            model=result.model_execution.model,
            prompt=result.prompt,
            structured_output=structured_output,
            fallback_used=result.model_execution.fallback_used,
            expected_sections=case.expected_sections or None,
        )

        searchable_text = self._build_searchable_text(
            output=result.model_execution.output,
            structured_output=structured_output,
        )
        matched_keywords = [
            keyword for keyword in case.expected_keywords if keyword.lower() in searchable_text
        ]
        missing_keywords = [
            keyword for keyword in case.expected_keywords if keyword.lower() not in searchable_text
        ]
        missing_sections = list(evaluation.metadata.get("missing_sections", []))
        passed = (
            evaluation.status == EvaluationStatus.PASSED
            and not missing_keywords
            and not missing_sections
        )

        return RegressionCaseResult(
            case_id=case.case_id,
            dataset_id=dataset.dataset_id,
            template_id=result.template_id,
            template_version=result.template_version,
            input_prompt=case.input_prompt,
            expected_keywords=list(case.expected_keywords),
            expected_sections=list(case.expected_sections),
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            missing_sections=missing_sections,
            passed=passed,
            score=evaluation.score or 0.0,
            latency_ms=result.model_execution.latency_ms,
            fallback_used=result.model_execution.fallback_used,
            evaluation_status=(
                evaluation.status if passed else EvaluationStatus.FAILED
            ),
            prompt_hash=result.prompt_hash,
            output=result.model_execution.output,
            structured_output=structured_output,
            metadata={
                **result.metadata,
                "project": project,
                "issue_id": request.issue_id,
                "evaluation": evaluation.model_dump(mode="json"),
            },
        )

    def _build_available_artifacts(
        self,
        *,
        template_id: str,
        case: PromptDatasetCase,
    ) -> dict[str, object]:
        if template_id == "pm_business_brief":
            return {
                "founder_input": {
                    "summary": case.input_prompt,
                }
            }

        available_artifacts = case.metadata.get("available_artifacts", {})
        return available_artifacts if isinstance(available_artifacts, dict) else {}

    def _build_searchable_text(
        self,
        *,
        output: str,
        structured_output: dict[str, object],
    ) -> str:
        return " ".join(
            [
                output.lower(),
                json.dumps(structured_output, ensure_ascii=True, sort_keys=True).lower(),
            ]
        )

    def _build_summary(
        self,
        cases: list[RegressionCaseResult],
    ) -> RegressionRunSummary:
        total = len(cases)
        passed = sum(1 for case in cases if case.passed)
        failed = total - passed
        avg_score = round(sum(case.score for case in cases) / total, 4) if total else 0.0
        avg_latency_ms = (
            round(sum(case.latency_ms for case in cases) / total, 2) if total else 0.0
        )
        return RegressionRunSummary(
            total=total,
            passed=passed,
            failed=failed,
            avg_score=avg_score,
            avg_latency_ms=avg_latency_ms,
        )
