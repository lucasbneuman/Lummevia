import json

from lummevia_core import AgentRole, DevelopmentWorkflowDefinition, WorkflowDefinition, WorkflowStep


def test_development_workflow_contains_expected_steps_in_order() -> None:
    workflow = DevelopmentWorkflowDefinition()

    assert [step.name for step in workflow.steps] == [
        "founder_input",
        "pm_business_brief",
        "po_execution_package",
        "dev_implementation",
        "qa_validation",
        "dev_qa_iteration",
        "github_pr",
        "qc_quality_approval",
        "po_final_validation",
    ]


def test_every_workflow_step_has_responsible_role() -> None:
    workflow = DevelopmentWorkflowDefinition()

    assert all(isinstance(step.responsible_role, AgentRole) for step in workflow.steps)


def test_every_workflow_step_declares_consumes_and_produces() -> None:
    workflow = DevelopmentWorkflowDefinition()

    for step in workflow.steps:
        assert isinstance(step.consumes, list)
        assert isinstance(step.produces, list)


def test_founder_input_step_uses_founder_role() -> None:
    workflow = DevelopmentWorkflowDefinition()

    founder_step = next(step for step in workflow.steps if step.name == "founder_input")

    assert founder_step.responsible_role == AgentRole.FOUNDER
    assert founder_step.consumes == ["founder_intent"]
    assert founder_step.produces == ["founder_input"]


def test_dev_qa_iteration_step_exists_explicitly() -> None:
    workflow = DevelopmentWorkflowDefinition()

    iteration_step = next(step for step in workflow.steps if step.name == "dev_qa_iteration")

    assert iteration_step.responsible_role == AgentRole.QA
    assert "ImplementationPackage" in iteration_step.consumes
    assert "ValidationPackage" in iteration_step.produces


def test_workflow_exports_to_dict_and_json() -> None:
    workflow = DevelopmentWorkflowDefinition()

    exported = workflow.model_dump(mode="json")
    exported_json = workflow.model_dump_json()

    assert exported["name"] == "development_loop"
    assert json.loads(exported_json)["steps"][0]["name"] == "founder_input"


def test_workflow_step_accepts_basic_payload() -> None:
    step = WorkflowStep(
        name="pm_business_brief",
        responsible_role=AgentRole.PM,
        consumes=["founder_input"],
        produces=["BusinessBrief"],
        description="Transform founder intent into a business brief.",
    )

    assert step.responsible_role == AgentRole.PM
    assert step.produces == ["BusinessBrief"]


def test_workflow_definition_accepts_basic_payload() -> None:
    workflow = WorkflowDefinition(
        name="custom_workflow",
        description="Simple contractual workflow.",
        steps=[
            WorkflowStep(
                name="qa_validation",
                responsible_role=AgentRole.QA,
                consumes=["ImplementationPackage"],
                produces=["ValidationPackage"],
                description="Validate implementation behavior.",
            )
        ],
    )

    assert workflow.name == "custom_workflow"
    assert workflow.steps[0].name == "qa_validation"
