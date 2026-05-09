from __future__ import annotations

from typing import Any

from pydantic import Field

from lummevia_core import (
    AgentRole,
    BusinessBrief,
    ExecutionPackage,
    ImplementationPackage,
    Priority,
    QualityApproval,
    ValidationPackage,
    ValidationStatus,
)
from lummevia_core.validation import CoreArtifactModel

from lummevia_agents.execution import ModelExecutionResult, ModelExecutor
from lummevia_agents.prompts.context import ContextBuilder, PromptContext
from lummevia_agents.prompts.registry import PromptRegistry
from lummevia_agents.schemas import AgentBaseSchema


ArtifactResult = (
    BusinessBrief
    | ExecutionPackage
    | ImplementationPackage
    | ValidationPackage
    | QualityApproval
)


class PromptExecutionRequest(AgentBaseSchema):
    role: AgentRole
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    target_artifact: str = Field(min_length=1)
    environment: str | None = None
    available_artifacts: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptExecutionResult(AgentBaseSchema):
    role: AgentRole
    target_artifact: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    context: PromptContext
    model_execution: ModelExecutionResult
    structured_output: ArtifactResult
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptPipeline:
    def __init__(
        self,
        *,
        registry: PromptRegistry | None = None,
        context_builder: ContextBuilder | None = None,
        model_executor: ModelExecutor | None = None,
    ) -> None:
        self.registry = registry or PromptRegistry.default()
        self.context_builder = context_builder or ContextBuilder()
        self.model_executor = model_executor or ModelExecutor()

    def execute(self, request: PromptExecutionRequest) -> PromptExecutionResult:
        template = self.registry.get_template(request.role, request.target_artifact)
        context = self.context_builder.build(
            project=request.project,
            issue_id=request.issue_id,
            role=request.role,
            available_artifacts=request.available_artifacts,
            metadata=request.metadata,
        )
        prompt = template.render(context)
        model_execution = self.model_executor.execute(
            request=self._build_model_request(request, prompt, template.system_prompt)
        )
        structured_output = self._build_fake_output(
            artifact_model=template.artifact_model,
            context=context,
        )
        metadata = dict(model_execution.metadata)
        metadata.update(
            {
                "target_artifact": request.target_artifact,
                "issue_id": request.issue_id,
            }
        )
        return PromptExecutionResult(
            role=request.role,
            target_artifact=request.target_artifact,
            prompt=prompt,
            system_prompt=template.system_prompt,
            context=context,
            model_execution=model_execution,
            structured_output=structured_output,
            metadata=metadata,
        )

    def _build_model_request(
        self,
        request: PromptExecutionRequest,
        prompt: str,
        system_prompt: str,
    ):
        from lummevia_agents.execution import ModelExecutionRequest

        return ModelExecutionRequest(
            role=request.role,
            project=request.project,
            environment=request.environment,
            prompt=prompt,
            system_prompt=system_prompt,
            metadata=request.metadata,
        )

    def _build_fake_output(
        self,
        *,
        artifact_model: type[CoreArtifactModel],
        context: PromptContext,
    ) -> ArtifactResult:
        builders: dict[type[CoreArtifactModel], Any] = {
            BusinessBrief: self._build_business_brief,
            ExecutionPackage: self._build_execution_package,
            ImplementationPackage: self._build_implementation_package,
            ValidationPackage: self._build_validation_package,
            QualityApproval: self._build_quality_approval,
        }
        builder = builders[artifact_model]
        return builder(context)

    def _build_business_brief(self, context: PromptContext) -> BusinessBrief:
        artifact_names = sorted(context.available_artifacts.keys()) or ["founder_input"]
        return BusinessBrief(
            issue_id=context.issue_id,
            project=context.project,
            objective=f"Clarify the business request for {context.issue_id}",
            problem="Prompt execution still lacks a dedicated pipeline layer.",
            expected_impact="Agents can render executable prompts with predictable outputs.",
            priority=Priority.HIGH,
            constraints=[
                "Keep providers fake-only",
                "Do not add HTTP integrations",
            ],
            non_goals=[
                "Connect real model providers",
                "Publish production prompt content",
            ],
            kpis=[
                f"Pipeline renders prompt for {context.role.value}",
                f"Context includes artifacts: {', '.join(artifact_names)}",
            ],
        )

    def _build_execution_package(self, context: PromptContext) -> ExecutionPackage:
        return ExecutionPackage(
            issue_id=context.issue_id,
            project=context.project,
            technical_story=(
                "Create a prompt pipeline that composes context, template, role, "
                "and target artifact before delegating execution to ModelExecutor."
            ),
            acceptance_criteria=[
                "Registry resolves template by role and artifact",
                "Context builder normalizes available artifacts",
                "Pipeline returns fake structured outputs validated by core schemas",
            ],
            edge_cases=[
                "Missing template fails explicitly",
                "Metadata survives model execution",
            ],
            testing_scenarios=[
                "PM produces BusinessBrief",
                "PO produces ExecutionPackage",
            ],
            architecture_decisions=[
                "Prompt templates live in packages/agents",
                "Structured outputs stay fake until real providers are introduced",
            ],
            task_checklist=[
                "Create prompt contracts",
                "Register default templates",
                "Add prompt pipeline tests",
            ],
            dev_prompts=[
                "Implement a fake prompt execution pipeline.",
                "Validate outputs against shared artifact contracts.",
            ],
        )

    def _build_implementation_package(
        self, context: PromptContext
    ) -> ImplementationPackage:
        return ImplementationPackage(
            issue_id=context.issue_id,
            project=context.project,
            branch="fake/prompt-pipeline",
            commits=["fake-commit-001"],
            files_changed=[
                "packages/agents/lummevia_agents/prompts/pipeline.py",
                "packages/agents/lummevia_agents/prompts/registry.py",
            ],
            tests_run=[
                "pytest -q tests/test_prompt_pipeline.py",
            ],
            summary=(
                "Implemented the first prompt execution pipeline using fake outputs "
                "and shared contracts."
            ),
            risks=[
                "Prompt wording is placeholder-only",
                "No real provider or structured LLM parsing exists yet",
            ],
        )

    def _build_validation_package(self, context: PromptContext) -> ValidationPackage:
        return ValidationPackage(
            issue_id=context.issue_id,
            project=context.project,
            status=ValidationStatus.PASSED,
            bugs_found=[],
            scenarios_validated=[
                "Prompt context rendering",
                "Fake structured output validation",
            ],
            feedback="Fake prompt pipeline behaves as expected for the covered roles.",
            risks=[
                "Real provider integration remains untested",
            ],
        )

    def _build_quality_approval(self, context: PromptContext) -> QualityApproval:
        return QualityApproval(
            issue_id=context.issue_id,
            project=context.project,
            status=ValidationStatus.PASSED,
            architecture_ok=True,
            standards_ok=True,
            pr_ok=True,
            observations=[
                "Pipeline is isolated in packages/agents",
                "Model selection remains delegated to model-router",
            ],
        )
