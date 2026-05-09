from lummevia_core import (
    AgentRole,
    BusinessBrief,
    ExecutionPackage,
    ImplementationPackage,
    QualityApproval,
    ValidationPackage,
)
from lummevia_agents import FakeModelProvider, ModelExecutor
from lummevia_agents.prompts import (
    ContextBuilder,
    PromptExecutionRequest,
    PromptPipeline,
    PromptRegistry,
    PromptTemplateNotFoundError,
)


def test_prompt_registry_returns_pm_template() -> None:
    registry = PromptRegistry.default()

    template = registry.get_template(AgentRole.PM, "BusinessBrief")

    assert template.role == AgentRole.PM
    assert template.target_artifact == "BusinessBrief"


def test_prompt_registry_returns_po_template() -> None:
    registry = PromptRegistry.default()

    template = registry.get_template(AgentRole.PO, "ExecutionPackage")

    assert template.role == AgentRole.PO
    assert template.target_artifact == "ExecutionPackage"


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
    assert result.model_execution.metadata["provider_adapter"] == "fake"
    assert isinstance(result.structured_output, BusinessBrief)
    assert result.structured_output.issue_id == "LUM-301"


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
                    non_goals=["Connect OpenRouter"],
                    kpis=["Pipeline returns fake structured output"],
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
    assert isinstance(implementation_package, ImplementationPackage)
    assert isinstance(validation_package, ValidationPackage)
    assert isinstance(quality_approval, QualityApproval)
