from fastapi import APIRouter, HTTPException, status

from lummevia_resources import ResourceLock, ResourceRegistry, WorkspaceAllocation


router = APIRouter(prefix="/resources", tags=["resources"])


@router.get("/locks", response_model=list[ResourceLock])
def list_resource_locks() -> list[ResourceLock]:
    return ResourceRegistry.default().list_locks()


@router.get("/workspaces", response_model=list[WorkspaceAllocation])
def list_workspaces() -> list[WorkspaceAllocation]:
    return ResourceRegistry.default().list_workspaces()


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceAllocation)
def get_workspace(workspace_id: str) -> WorkspaceAllocation:
    workspace = ResourceRegistry.default().get_workspace(workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace_id}' not found.",
        )
    return workspace
