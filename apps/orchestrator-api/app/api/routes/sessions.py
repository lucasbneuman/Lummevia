from fastapi import APIRouter, HTTPException, status

from lummevia_sessions import SessionRegistry, TaskExecutionSession


router = APIRouter(prefix="/sessions", tags=["sessions"])


def _get_session_registry() -> SessionRegistry:
    return SessionRegistry.default()


@router.get("", response_model=list[TaskExecutionSession])
def list_sessions() -> list[TaskExecutionSession]:
    return _get_session_registry().list_sessions()


@router.get("/{session_id}", response_model=TaskExecutionSession)
def get_session(session_id: str) -> TaskExecutionSession:
    session = _get_session_registry().get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return session
