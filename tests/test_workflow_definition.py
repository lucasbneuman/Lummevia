import json

from lummevia_core import AgentRole, DevelopmentWorkflowDefinition, WorkflowDefinition, WorkflowStep


def test_development_workflow_contains_expected_steps_in_order() -> None:
    workflow = DevelopmentWorkflowDefinition()

    assert [step.name for step in workflow.steps] == [
        "founder_input",
        "founder_pm_conversation",
        "pm_business_brief",
        "founder_business_approval",
        "po_execution_package",
        "po_task_plan",
        "po_task_packages",
        "dev_implementation",
        "qa_validation",
        "dev_qa_iteration",
        "workflow_completed",
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


def test_workflow_completed_step_closes_the_contractual_lifecycle() -> None:
    workflow = DevelopmentWorkflowDefinition()

    completion_step = next(step for step in workflow.steps if step.name == "workflow_completed")

    assert completion_step.responsible_role == AgentRole.QA
    assert "ValidationPackage" in completion_step.consumes
    assert completion_step.produces == ["WorkflowCompleted"]


def test_founder_approval_step_happens_before_po_execution_package() -> None:
    workflow = DevelopmentWorkflowDefinition()

    step_names = [step.name for step in workflow.steps]

    assert step_names.index("founder_pm_conversation") < step_names.index("pm_business_brief")
    assert step_names.index("pm_business_brief") < step_names.index(
        "founder_business_approval"
    )
    assert step_names.index("founder_business_approval") < step_names.index(
        "po_execution_package"
    )
    assert step_names.index("po_execution_package") < step_names.index("po_task_plan")
    assert step_names.index("po_task_plan") < step_names.index("po_task_packages")
    assert step_names.index("po_task_packages") < step_names.index("dev_implementation")


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
