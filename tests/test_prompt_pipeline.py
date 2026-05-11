from lummevia_core import (
    AgentRole,
    BusinessBrief,
    ExecutionPackage,
    ImplementationPackage,
    QualityApproval,
    TaskPackage,
    TaskPlan,
    ValidationPackage,
)
from lummevia_agents import FakeModelProvider, ModelExecutor
from lummevia_agents.prompts import (
    ContextBuilder,
    PromptExecutionRequest,
    PromptPipeline,
    PromptRegistry,
    PromptTemplate,
    PromptTemplateNotFoundError,
)
from lummevia_agents.prompts.templates import build_default_templates
from lummevia_evaluations import PromptBaselineRegistry
from lummevia_evaluations import EvaluationStatus


def build_regression_run_for_test(*, template_version: str):
    from datetime import UTC, datetime

    from lummevia_evaluations import RegressionRunResult, RegressionRunSummary

    now = datetime.now(UTC)
    return RegressionRunResult(
        regression_run_id=f"regr-{template_version}",
        template_id="pm_business_brief",
        template_version=template_version,
        dataset_id="pm_business_brief_dataset",
        summary=RegressionRunSummary(
            total=5,
            passed=5,
            failed=0,
            avg_score=0.9,
            avg_latency_ms=110.0,
        ),
        cases=[],
        started_at=now,
        completed_at=now,
    )


def test_prompt_registry_returns_pm_template() -> None:
    registry = PromptRegistry.default()

    template = registry.get_template(AgentRole.PM, "BusinessBrief")

    assert template.role == AgentRole.PM
    assert template.target_artifact == "BusinessBrief"
    assert template.template_id == "pm_business_brief"
    assert template.version == "v1"


def test_prompt_registry_returns_po_template() -> None:
    registry = PromptRegistry.default()

    template = registry.get_template(AgentRole.PO, "ExecutionPackage")

    assert template.role == AgentRole.PO
    assert template.target_artifact == "ExecutionPackage"


def test_prompt_registry_returns_po_task_plan_template() -> None:
    registry = PromptRegistry.default()

    template = registry.get_template(AgentRole.PO, "TaskPlan")

    assert template.role == AgentRole.PO
    assert template.target_artifact == "TaskPlan"


def test_prompt_registry_resolves_active_baseline_version_when_no_version_is_provided() -> None:
    baseline_registry = PromptBaselineRegistry()
    templates = build_default_templates()
    templates.append(
        PromptTemplate(
            template_id="pm_business_brief",
            version="v2",
            role=AgentRole.PM,
            target_artifact="BusinessBrief",
            artifact_model=BusinessBrief,
            system_prompt="You are the PM role in Lummevia OS.",
            instructions="A promoted version for active resolution tests.",
        )
    )
    registry = PromptRegistry(templates, baseline_registry=baseline_registry)
    baseline_registry.promote(
        template_id="pm_business_brief",
        candidate_version="v1",
        regression_run=build_regression_run_for_test(template_version="v1"),
    )

    active_template = registry.get_template(AgentRole.PM, "BusinessBrief")
    explicit_template = registry.get_template(
        AgentRole.PM,
        "BusinessBrief",
        version="v2",
    )

    assert active_template.version == "v1"
    assert explicit_template.version == "v2"


def test_prompt_registry_raises_clear_error_for_missing_template() -> None:
    registry = PromptRegistry.default()

    try:
        registry.get_template(AgentRole.DEV, "BusinessBrief")
    except PromptTemplateNotFoundError as exc:
        assert str(exc) == (
            "No prompt template registered for role 'DEV' "
            "and target artifact 'BusinessBrief'."
        )
    else:
        raise AssertionError("Expected PromptTemplateNotFoundError")


def test_context_builder_builds_minimal_context() -> None:
    context = ContextBuilder().build(
        project="lummevia-os",
        issue_id="LUM-201",
        role=AgentRole.PM,
        available_artifacts={
            "founder_input": {"summary": "Improve prompt orchestration"}
        },
        metadata={"trace_id": "trace-123"},
    )

    assert context.project == "lummevia-os"
    assert context.issue_id == "LUM-201"
    assert context.role == AgentRole.PM
    assert context.available_artifacts["founder_input"]["summary"] == (
        "Improve prompt orchestration"
    )
    assert context.metadata["trace_id"] == "trace-123"


def test_prompt_pipeline_executes_pm_to_business_brief_fake() -> None:
    pipeline = PromptPipeline(
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )

    result = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PM,
            project="lummevia-os",
            issue_id="LUM-301",
            target_artifact="BusinessBrief",
            metadata={"trace_id": "trace-pm"},
        )
    )

    assert result.target_artifact == "BusinessBrief"
    assert result.template_id == "pm_business_brief"
    assert result.template_version == "v1"
    assert len(result.prompt_hash) == 64
    assert result.model_execution.metadata["provider_adapter"] == "fake"
    assert isinstance(result.structured_output, BusinessBrief)
    assert result.structured_output.issue_id == "LUM-301"
    assert result.structured_output.business_brief_status == "draft"
    assert result.structured_output.founder_approved is False
    assert result.evaluation_status == EvaluationStatus.PENDING


def test_prompt_pipeline_executes_po_to_execution_package_fake() -> None:
    pipeline = PromptPipeline(
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )

    result = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PO,
            project="lummevia-os",
            issue_id="LUM-302",
            target_artifact="ExecutionPackage",
            available_artifacts={
                "business_brief": BusinessBrief(
                    issue_id="LUM-302",
                    project="lummevia-os",
                    objective="Improve prompt orchestration",
                    problem="Prompt execution is not centralized",
                    expected_impact="More consistent agent handoffs",
                    priority="HIGH",
                    constraints=["No real providers"],
                    non_goals=["Connect DeepSeek runtime beyond PM dry-run"],
                    kpis=["Pipeline returns fake structured output"],
                    business_brief_status="approved",
                    founder_approved=True,
                )
            },
            metadata={"trace_id": "trace-po"},
        )
    )

    assert result.target_artifact == "ExecutionPackage"
    assert isinstance(result.structured_output, ExecutionPackage)
    assert result.structured_output.issue_id == "LUM-302"


def test_prompt_pipeline_propagates_metadata() -> None:
    pipeline = PromptPipeline(
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )

    result = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.QA,
            project="lummevia-os",
            issue_id="LUM-303",
            target_artifact="ValidationPackage",
            metadata={"run_id": "run-303", "trace_id": "trace-qa"},
        )
    )

    assert result.metadata["run_id"] == "run-303"
    assert result.metadata["trace_id"] == "trace-qa"
    assert result.metadata["target_artifact"] == "ValidationPackage"
    assert result.metadata["template_id"] == "qa_validation_package"
    assert result.metadata["template_version"] == "v1"
    assert result.metadata["prompt_hash"] == result.prompt_hash


def test_prompt_pipeline_prompt_hash_is_deterministic() -> None:
    pipeline = PromptPipeline(
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )

    first = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PM,
            project="lummevia-os",
            issue_id="LUM-303A",
            target_artifact="BusinessBrief",
            metadata={"trace_id": "trace-hash"},
        )
    )
    second = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PM,
            project="lummevia-os",
            issue_id="LUM-303A",
            target_artifact="BusinessBrief",
            metadata={"trace_id": "trace-hash"},
        )
    )

    assert first.prompt == second.prompt
    assert first.prompt_hash == second.prompt_hash


def test_prompt_pipeline_uses_explicit_template_version_when_requested() -> None:
    baseline_registry = PromptBaselineRegistry()
    templates = build_default_templates()
    templates.append(
        PromptTemplate(
            template_id="pm_business_brief",
            version="v2",
            role=AgentRole.PM,
            target_artifact="BusinessBrief",
            artifact_model=BusinessBrief,
            system_prompt="You are the PM role in Lummevia OS.",
            instructions="Use the candidate v2 PM prompt.",
        )
    )
    pipeline = PromptPipeline(
        registry=PromptRegistry(templates, baseline_registry=baseline_registry),
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )

    result = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PM,
            project="lummevia-os",
            issue_id="LUM-303B",
            target_artifact="BusinessBrief",
            template_version="v2",
            metadata={"trace_id": "trace-explicit-version"},
        )
    )

    assert result.template_version == "v2"


def test_prompt_pipeline_executes_po_to_task_plan_fake() -> None:
    pipeline = PromptPipeline(
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )

    result = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PO,
            project="lummevia-os",
            issue_id="LUM-302A",
            target_artifact="TaskPlan",
            available_artifacts={
                "execution_package": ExecutionPackage(
                    issue_id="LUM-302A",
                    project="lummevia-os",
                    technical_story="Decompose PO output into smaller task packages",
                    acceptance_criteria=["TaskPlan exists"],
                    edge_cases=["No monolithic prompt"],
                    testing_scenarios=["Pipeline builds TaskPlan"],
                    architecture_decisions=["Keep contracts simple"],
                    task_checklist=["Create contracts", "Update runtime"],
                    dev_prompts=["Create TaskPlan prompt template"],
                )
            },
            metadata={"trace_id": "trace-po-plan"},
        )
    )

    assert result.target_artifact == "TaskPlan"
    assert isinstance(result.structured_output, TaskPlan)
    assert len(result.structured_output.task_packages) >= 2


def test_prompt_pipeline_executes_po_to_task_package_fake() -> None:
    pipeline = PromptPipeline(
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )

    result = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PO,
            project="lummevia-os",
            issue_id="LUM-302B",
            target_artifact="TaskPackage",
            available_artifacts={
                "task_plan": TaskPlan(
                    issue_id="LUM-302B",
                    project="lummevia-os",
                    workstreams=["runtime"],
                    task_packages=["LUM-302B-T1", "LUM-302B-T2"],
                    sequencing_notes=["Process runtime first"],
                    risks=["Plan can diverge from implementation"],
                )
            },
            metadata={
                "trace_id": "trace-po-task",
                "task_id": "LUM-302B-T1",
                "task_index": 0,
            },
        )
    )

    assert result.target_artifact == "TaskPackage"
    assert isinstance(result.structured_output, TaskPackage)
    assert result.structured_output.task_id == "LUM-302B-T1"


def test_prompt_pipeline_uses_fake_model_provider() -> None:
    pipeline = PromptPipeline(
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )

    result = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.QC,
            project="lummevia-os",
            issue_id="LUM-304",
            target_artifact="QualityApproval",
            metadata={},
        )
    )

    assert result.model_execution.raw_output["provider_adapter"] == "fake"


def test_prompt_pipeline_fake_outputs_validate_against_artifacts() -> None:
    pipeline = PromptPipeline(
        model_executor=ModelExecutor(provider=FakeModelProvider()),
    )

    business_brief = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PM,
            project="lummevia-os",
            issue_id="LUM-401",
            target_artifact="BusinessBrief",
            metadata={},
        )
    ).structured_output
    execution_package = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PO,
            project="lummevia-os",
            issue_id="LUM-402",
            target_artifact="ExecutionPackage",
            metadata={},
        )
    ).structured_output
    task_plan = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PO,
            project="lummevia-os",
            issue_id="LUM-402A",
            target_artifact="TaskPlan",
            available_artifacts={"execution_package": execution_package},
            metadata={},
        )
    ).structured_output
    task_package = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.PO,
            project="lummevia-os",
            issue_id="LUM-402B",
            target_artifact="TaskPackage",
            available_artifacts={"task_plan": task_plan},
            metadata={"task_id": "LUM-402B-T1", "task_index": 0},
        )
    ).structured_output
    implementation_package = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.DEV,
            project="lummevia-os",
            issue_id="LUM-403",
            target_artifact="ImplementationPackage",
            metadata={},
        )
    ).structured_output
    validation_package = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.QA,
            project="lummevia-os",
            issue_id="LUM-404",
            target_artifact="ValidationPackage",
            metadata={},
        )
    ).structured_output
    quality_approval = pipeline.execute(
        PromptExecutionRequest(
            role=AgentRole.QC,
            project="lummevia-os",
            issue_id="LUM-405",
            target_artifact="QualityApproval",
            metadata={},
        )
    ).structured_output

    assert isinstance(business_brief, BusinessBrief)
    assert isinstance(execution_package, ExecutionPackage)
    assert isinstance(task_plan, TaskPlan)
    assert isinstance(task_package, TaskPackage)
    assert isinstance(implementation_package, ImplementationPackage)
    assert isinstance(validation_package, ValidationPackage)
    assert isinstance(quality_approval, QualityApproval)
