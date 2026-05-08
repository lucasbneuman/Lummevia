from fastapi import APIRouter, HTTPException, status

from lummevia_core import DevelopmentWorkflowDefinition, WorkflowStep


router = APIRouter(prefix="/workflows", tags=["workflows"])


def get_development_workflow() -> DevelopmentWorkflowDefinition:
    return DevelopmentWorkflowDefinition()


@router.get("/development", response_model=DevelopmentWorkflowDefinition)
def get_development_workflow_definition() -> DevelopmentWorkflowDefinition:
    return get_development_workflow()


@router.get("/development/steps", response_model=list[WorkflowStep])
def list_development_workflow_steps() -> list[WorkflowStep]:
    return get_development_workflow().steps


@router.get("/development/steps/{step_name}", response_model=WorkflowStep)
def get_development_workflow_step(step_name: str) -> WorkflowStep:
    workflow = get_development_workflow()

    for step in workflow.steps:
        if step.name == step_name:
            return step

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Workflow step '{step_name}' not found.",
    )
