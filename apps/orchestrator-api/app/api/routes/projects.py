from fastapi import APIRouter, HTTPException, status

from lummevia_core import ApprovedProjectHandoff, ApprovedProjectHandoffRegistry


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/handoffs", response_model=list[ApprovedProjectHandoff])
def list_project_handoffs(project: str | None = None) -> list[ApprovedProjectHandoff]:
    return ApprovedProjectHandoffRegistry.default().list_handoffs(project=project)


@router.get("/handoffs/{handoff_id}", response_model=ApprovedProjectHandoff)
def get_project_handoff(handoff_id: str) -> ApprovedProjectHandoff:
    handoff = ApprovedProjectHandoffRegistry.default().get_handoff(handoff_id)
    if handoff is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project handoff '{handoff_id}' not found.",
        )
    return handoff
