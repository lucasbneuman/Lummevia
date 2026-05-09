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
        founder_input = context.available_artifacts.get("founder_input", {})
        founder_summary = founder_input.get(
            "summary",
            f"Initial founder intent captured for issue {context.issue_id}.",
        )
        return BusinessBrief(
            issue_id=context.issue_id,
            project=context.project,
            objective=f"Clarify and advance the founder request for {context.issue_id}",
            problem=founder_summary,
            expected_impact=(
                "Enable the runtime to delegate artifact generation through agents "
                "and the prompt pipeline."
            ),
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
        business_brief = context.available_artifacts.get("business_brief", {})
        return ExecutionPackage(
            issue_id=context.issue_id,
            project=context.project,
            technical_story=(
                "Connect the simulated runtime nodes to agents that delegate "
                "artifact production through PromptPipeline and FakeModelProvider. "
                f"Business objective: {business_brief.get('objective', 'not supplied')}."
            ),
            acceptance_criteria=[
                "Runtime PM node delegates BusinessBrief generation to PMAgent",
                "Runtime PO, DEV, QA, and QC nodes produce artifacts via PromptPipeline",
                "Pipeline returns fake structured outputs validated by core schemas",
            ],
            edge_cases=[
                "Missing template fails explicitly",
                "QA outcome changes according to loop_count metadata",
            ],
            testing_scenarios=[
                "PM produces BusinessBrief",
                "Runtime completes DEV-QA loop before PR creation",
            ],
            architecture_decisions=[
                "Prompt templates live in packages/agents",
                "Structured outputs stay fake until real providers are introduced",
            ],
            task_checklist=[
                "Delegate runtime artifact creation to agents",
                "Preserve runtime persistence and Phoenix instrumentation",
                "Keep github_pr as a separate simulated node",
            ],
            dev_prompts=[
                "Implement runtime to agent to pipeline delegation using fake providers only.",
                "Validate outputs against shared artifact contracts.",
            ],
        )

    def _build_implementation_package(
        self, context: PromptContext
    ) -> ImplementationPackage:
        loop_count = int(context.metadata.get("loop_count", 0))
        is_rework = loop_count > 0
        return ImplementationPackage(
            issue_id=context.issue_id,
            project=context.project,
            branch=f"runtime/{context.issue_id.lower()}",
            commits=(
                ["simulated-initial-commit", "simulated-rework-commit"]
                if is_rework
                else ["simulated-initial-commit"]
            ),
            files_changed=[
                "packages/runtime/lummevia_runtime/graph.py",
                "packages/agents/lummevia_agents/base.py",
            ],
            tests_run=[
                "pytest -q tests/test_prompt_pipeline.py",
                "pytest -q tests/test_runtime_graph.py",
            ],
            summary=(
                "Applied implementation rework after QA feedback."
                if is_rework
                else "Created initial simulated implementation package through the prompt pipeline."
            ),
            risks=[
                "Prompt wording is placeholder-only",
                "No real provider or structured LLM parsing exists yet",
            ],
        )

    def _build_validation_package(self, context: PromptContext) -> ValidationPackage:
        loop_count = int(context.metadata.get("loop_count", 0))
        first_pass = loop_count == 0
        status = ValidationStatus.FAILED if first_pass else ValidationStatus.PASSED
        implementation_package = context.available_artifacts.get(
            "implementation_package",
            {},
        )
        scenarios_validated = [
            "Prompt context rendering",
            "Fake structured output validation",
            f"Implementation branch {implementation_package.get('branch', 'unknown')}",
        ]
        if not first_pass:
            scenarios_validated.append("DEV-QA rework loop resolution")
        return ValidationPackage(
            issue_id=context.issue_id,
            project=context.project,
            status=status,
            bugs_found=["BUG-DEV-QA-LOOP"] if first_pass else [],
            scenarios_validated=scenarios_validated,
            feedback=(
                "QA found issues and requested a DEV rework iteration."
                if first_pass
                else "QA validated the implementation after the rework loop."
            ),
            risks=(
                ["Implementation requires rework before QC"]
                if first_pass
                else ["Real provider integration remains untested"]
            ),
        )

    def _build_quality_approval(self, context: PromptContext) -> QualityApproval:
        pull_request = context.available_artifacts.get("pull_request", {})
        pr_ok = pull_request.get("status") == "OPEN"
        return QualityApproval(
            issue_id=context.issue_id,
            project=context.project,
            status=ValidationStatus.PASSED,
            architecture_ok=True,
            standards_ok=True,
            pr_ok=pr_ok,
            observations=[
                "Pipeline is isolated in packages/agents",
                "Model selection remains delegated to model-router",
                (
                    f"QC reviewed simulated PR #{pull_request['pr_number']}."
                    if pull_request.get("pr_number") is not None
                    else "QC did not find a simulated PR."
                ),
            ],
        )
