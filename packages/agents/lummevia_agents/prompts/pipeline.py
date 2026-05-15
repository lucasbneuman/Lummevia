from __future__ import annotations

from hashlib import sha256
from typing import Any

from pydantic import Field

from lummevia_core import (
    AgentRole,
    BusinessBrief,
    ExecutionPackage,
    ImplementationPackage,
    Priority,
    QualityApproval,
    TaskPackage,
    TaskPlan,
    ValidationPackage,
    ValidationStatus,
)
from lummevia_core.validation import CoreArtifactModel

from lummevia_agents.execution import ModelExecutionResult, ModelExecutor
from lummevia_agents.prompts.context import ContextBuilder, PromptContext
from lummevia_agents.prompts.registry import PromptRegistry
from lummevia_agents.schemas import AgentBaseSchema
from lummevia_evaluations import EvaluationStatus


ArtifactResult = (
    BusinessBrief
    | ExecutionPackage
    | TaskPlan
    | TaskPackage
    | ImplementationPackage
    | ValidationPackage
    | QualityApproval
)


class PromptExecutionRequest(AgentBaseSchema):
    role: AgentRole
    project: str = Field(min_length=1)
    issue_id: str = Field(min_length=1)
    target_artifact: str = Field(min_length=1)
    template_version: str | None = Field(default=None, min_length=1)
    environment: str | None = None
    available_artifacts: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptExecutionResult(AgentBaseSchema):
    role: AgentRole
    target_artifact: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    template_version: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    prompt_hash: str = Field(min_length=64, max_length=64)
    system_prompt: str = Field(min_length=1)
    context: PromptContext
    model_execution: ModelExecutionResult
    structured_output: ArtifactResult
    evaluation_id: str | None = None
    evaluation_status: EvaluationStatus = EvaluationStatus.PENDING
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
        template = self.registry.get_template(
            request.role,
            request.target_artifact,
            version=request.template_version,
        )
        context = self.context_builder.build(
            project=request.project,
            issue_id=request.issue_id,
            role=request.role,
            available_artifacts=request.available_artifacts,
            metadata=request.metadata,
        )
        prompt = template.render(context)
        prompt_hash = self._compute_prompt_hash(prompt)
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
                "template_id": template.template_id,
                "template_version": template.version,
                "prompt_hash": prompt_hash,
                "evaluation_id": None,
                "evaluation_status": EvaluationStatus.PENDING,
            }
        )
        if model_execution.raw_output is not None:
            metadata["model_raw_output"] = model_execution.raw_output
        return PromptExecutionResult(
            role=request.role,
            target_artifact=request.target_artifact,
            template_id=template.template_id,
            template_version=template.version,
            prompt=prompt,
            prompt_hash=prompt_hash,
            system_prompt=template.system_prompt,
            context=context,
            model_execution=model_execution,
            structured_output=structured_output,
            metadata=metadata,
        )

    def _compute_prompt_hash(self, prompt: str) -> str:
        return sha256(prompt.encode("utf-8")).hexdigest()

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
            TaskPlan: self._build_task_plan,
            TaskPackage: self._build_task_package,
            ImplementationPackage: self._build_implementation_package,
            ValidationPackage: self._build_validation_package,
            QualityApproval: self._build_quality_approval,
        }
        builder = builders[artifact_model]
        return builder(context)

    def _build_business_brief(self, context: PromptContext) -> BusinessBrief:
        artifact_names = sorted(context.available_artifacts.keys()) or ["founder_input"]
        founder_input = self._artifact_data(
            context.available_artifacts.get("founder_input")
        )
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
            business_brief_status="draft",
            founder_approved=False,
        )

    def _build_execution_package(self, context: PromptContext) -> ExecutionPackage:
        business_brief = self._artifact_data(
            context.available_artifacts.get("business_brief")
        )
        return ExecutionPackage(
            issue_id=context.issue_id,
            project=context.project,
            technical_story=(
                "Connect the simulated runtime nodes to agents that delegate "
                "artifact production through PromptPipeline and FakeModelProvider. "
                f"Business objective: {business_brief.get('objective', 'not supplied')}. "
                "Founder approval is required before this package is created."
            ),
            acceptance_criteria=[
                "Runtime PM node delegates BusinessBrief generation to PMAgent",
                "Founder approval happens before the PO execution package node",
                "PO produces ExecutionPackage, TaskPlan, and TaskPackages in sequence",
                "Runtime PO, DEV, QA, and QC nodes produce artifacts via PromptPipeline",
                "Pipeline returns fake structured outputs validated by core schemas",
            ],
            edge_cases=[
                "Missing template fails explicitly",
                "QA outcome changes according to loop_count metadata",
                "PO must not execute from a draft business brief",
                "DEV should consume a TaskPackage instead of a monolithic prompt",
            ],
            testing_scenarios=[
                "Founder and PM iterate before drafting the BusinessBrief",
                "Founder approves the BusinessBrief before PO execution",
                "PO decomposes the approved brief into TaskPlan and TaskPackages",
                "Runtime completes DEV-QA loop before PR creation",
            ],
            architecture_decisions=[
                "Prompt templates live in packages/agents",
                "Structured outputs stay fake until real providers are introduced",
                "PO decomposition stays sequential until parallel execution is designed",
            ],
            task_checklist=[
                "Simulate founder to PM conversation and founder approval gates",
                "Delegate PO decomposition artifact creation to agents",
                "Preserve runtime persistence and Phoenix instrumentation",
                "Keep github_pr as a separate simulated node",
            ],
            dev_prompts=[
                "Implement runtime to agent to pipeline delegation using fake providers only.",
                "Validate outputs against shared artifact contracts.",
            ],
        )

    def _build_task_plan(self, context: PromptContext) -> TaskPlan:
        execution_package = self._artifact_data(
            context.available_artifacts.get("execution_package")
        )
        issue_slug = context.issue_id.upper()
        workstreams = self._determine_task_buckets(execution_package)
        return TaskPlan(
            issue_id=context.issue_id,
            project=context.project,
            workstreams=workstreams,
            task_packages=[
                f"{issue_slug}-{bucket[:3].upper()}-{index + 1}"
                for index, bucket in enumerate(workstreams)
            ],
            sequencing_notes=[
                f"Keep bucket ordering deterministic: {', '.join(workstreams)}.",
                "Run one TaskPackage at a time through the real queue and QA gate.",
                "Only advance to the next TaskPackage after QA PASS unlocks dependencies.",
            ],
            risks=[
                "Simulated task packages can drift from future provider-backed prompts",
                (
                    "Task granularity must stay small enough for Kilo CLI without "
                    "fragmenting traceability"
                ),
                (
                    "Execution package summary remains the umbrella context: "
                    f"{execution_package.get('technical_story', 'not supplied')}"
                ),
            ],
        )

    def _build_task_package(self, context: PromptContext) -> TaskPackage:
        task_plan = self._artifact_data(context.available_artifacts.get("task_plan"))
        task_id = str(context.metadata.get("task_id", f"{context.issue_id}-T1"))
        task_index = int(context.metadata.get("task_index", 0))
        buckets = task_plan.get("workstreams", []) or ["Backend"]
        bucket = str(buckets[min(task_index, len(buckets) - 1)])
        title = f"{bucket} lifecycle task"
        objective = self._task_objective_for_bucket(bucket)
        dependencies = [str(previous_task_id) for previous_task_id in task_plan.get("task_packages", [])[:task_index]]
        priority = "HIGH" if task_index == 0 else "NORMAL"
        return TaskPackage(
            task_id=task_id,
            issue_id=context.issue_id,
            project=context.project,
            title=title,
            description=(
                f"Deliver the {bucket} slice of the approved brief through the contractual "
                "PO -> DEV -> QA lifecycle."
            ),
            objective=objective,
            target_repo=context.project,
            context_refs=[
                "docs/02-agentes/roles-y-limites.md",
                "docs/03-workflows/loop-desarrollo.md",
                "packages/runtime/lummevia_runtime",
            ],
            acceptance_criteria=[
                "TaskPackage is small enough to execute in one focused DEV iteration",
                "DEV consumes this TaskPackage instead of a mega prompt",
                "QA validates acceptance criteria at the TaskPackage level",
            ],
            constraints=[
                "Keep providers fake",
                "Do not create real YouTrack tickets",
                "Do not introduce parallel execution yet",
                "Preserve Founder approval before PO execution",
            ],
            prompt=(
                "Implement only this TaskPackage using the execution package as "
                "umbrella context and keep changes traceable."
            ),
            expected_artifacts=[
                "ImplementationPackage",
                "ValidationPackage",
            ],
            status=(
                "in_progress"
                if task_index == 0
                else "planned"
            ),
            metadata={
                "bucket": bucket,
                "priority": priority,
                "dependencies": dependencies,
            },
        )

    def _build_implementation_package(
        self, context: PromptContext
    ) -> ImplementationPackage:
        loop_count = int(context.metadata.get("loop_count", 0))
        is_rework = loop_count > 0
        task_package = self._artifact_data(
            context.available_artifacts.get("task_package")
        )
        task_id = task_package.get("task_id", "unknown-task")
        task_title = task_package.get("title", "unknown task package")
        return ImplementationPackage(
            issue_id=context.issue_id,
            project=context.project,
            task_id=task_id,
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
                f"Applied implementation rework for task package {task_id} after QA feedback."
                if is_rework
                else (
                    "Created initial simulated implementation package through the "
                    f"prompt pipeline for task package {task_id}: {task_title}."
                )
            ),
            risks=[
                "Prompt wording is placeholder-only",
                "No real provider or structured LLM parsing exists yet",
            ],
            implementation_notes=[
                f"Task bucket: {task_package.get('metadata', {}).get('bucket', 'unknown')}",
                f"Task objective: {task_package.get('objective', 'not supplied')}",
            ],
        )

    def _build_validation_package(self, context: PromptContext) -> ValidationPackage:
        loop_count = int(context.metadata.get("loop_count", 0))
        first_pass = loop_count == 0
        status = ValidationStatus.FAILED if first_pass else ValidationStatus.PASSED
        implementation_package = self._artifact_data(
            context.available_artifacts.get("implementation_package")
        )
        task_package = self._artifact_data(
            context.available_artifacts.get("task_package")
        )
        scenarios_validated = [
            "Prompt context rendering",
            "Fake structured output validation",
            f"Implementation branch {implementation_package.get('branch', 'unknown')}",
            f"Task package {task_package.get('task_id', 'unknown-task')}",
        ]
        if not first_pass:
            scenarios_validated.append("DEV-QA rework loop resolution")
        return ValidationPackage(
            issue_id=context.issue_id,
            project=context.project,
            task_id=task_package.get("task_id", context.issue_id),
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
            findings=["Dependency or flow issue detected"] if first_pass else [],
            recommendation=(
                "Rework implementation before advancing to the next task."
                if first_pass
                else "Advance the next unlocked task package."
            ),
        )

    def _build_quality_approval(self, context: PromptContext) -> QualityApproval:
        pull_request = self._artifact_data(context.available_artifacts.get("pull_request"))
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

    def _artifact_data(self, artifact: Any | None) -> dict[str, Any]:
        if artifact is None:
            return {}
        if isinstance(artifact, CoreArtifactModel):
            return artifact.model_dump(mode="json")
        if isinstance(artifact, dict):
            return artifact
        return {}

    def _determine_task_buckets(self, execution_package: dict[str, Any]) -> list[str]:
        combined_text = " ".join(
            str(value)
            for value in execution_package.values()
            if isinstance(value, (str, list))
        ).lower()
        ordered_buckets = [
            ("Frontend", ("frontend", "ui", "ux", "telegram", "web")),
            ("Backend", ("backend", "runtime", "queue", "session", "workflow", "api")),
            ("Infra", ("infra", "docker", "phoenix", "observability", "deployment")),
            ("QA", ("qa", "validation", "testing", "test")),
            ("Documentation", ("documentation", "readme", "docs", "adr")),
        ]
        selected = [
            bucket
            for bucket, keywords in ordered_buckets
            if any(keyword in combined_text for keyword in keywords)
        ]
        if "Backend" not in selected:
            selected.insert(0, "Backend")
        if "QA" not in selected:
            selected.append("QA")
        if "Documentation" not in selected:
            selected.append("Documentation")
        return selected

    def _task_objective_for_bucket(self, bucket: str) -> str:
        objectives = {
            "Frontend": "Implement the Founder-visible interface changes required by the approved brief.",
            "Backend": "Implement the runtime, queue, session, and workflow logic for the approved brief.",
            "Infra": "Align infrastructure, observability, and environment wiring with the approved brief.",
            "QA": "Strengthen validation coverage and release gates for the approved brief.",
            "Documentation": "Document the lifecycle, contracts, and operational visibility for the approved brief.",
        }
        return objectives.get(bucket, "Implement the approved brief in a traceable task package.")
