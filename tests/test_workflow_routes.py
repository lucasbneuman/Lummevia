from fastapi.testclient import TestClient

from lummevia_core import DevelopmentWorkflowDefinition
from main import app


client = TestClient(app)


def test_workflows_development_returns_full_definition() -> None:
    workflow = DevelopmentWorkflowDefinition()

    response = client.get("/workflows/development")

    assert response.status_code == 200
    assert response.json() == workflow.model_dump(mode="json")


def test_workflows_development_steps_returns_ordered_steps() -> None:
    workflow = DevelopmentWorkflowDefinition()

    response = client.get("/workflows/development/steps")

    assert response.status_code == 200
    assert response.json() == [
        step.model_dump(mode="json")
        for step in workflow.steps
    ]


def test_workflows_development_founder_input_returns_step() -> None:
    workflow = DevelopmentWorkflowDefinition()
    founder_step = next(step for step in workflow.steps if step.name == "founder_input")

    response = client.get("/workflows/development/steps/founder_input")

    assert response.status_code == 200
    assert response.json() == founder_step.model_dump(mode="json")


def test_workflows_development_dev_qa_iteration_returns_step() -> None:
    workflow = DevelopmentWorkflowDefinition()
    iteration_step = next(step for step in workflow.steps if step.name == "dev_qa_iteration")

    response = client.get("/workflows/development/steps/dev_qa_iteration")

    assert response.status_code == 200
    assert response.json() == iteration_step.model_dump(mode="json")


def test_workflows_development_unknown_step_returns_404() -> None:
    response = client.get("/workflows/development/steps/unknown_step")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Workflow step 'unknown_step' not found.",
    }
