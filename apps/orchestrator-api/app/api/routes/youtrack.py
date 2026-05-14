from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.youtrack import ensure_youtrack_available
from lummevia_integrations import (
    AgentContextBundle,
    YouTrackComment,
    YouTrackCommentPayload,
    YouTrackConfigurationError,
    YouTrackIssue,
    YouTrackIssueCreatePayload,
    YouTrackIssueUpdatePayload,
    YouTrackKnowledgeDocument,
    YouTrackKnowledgeDocumentUpsertPayload,
)


router = APIRouter(prefix="/youtrack", tags=["youtrack"])


class IssueSearchResponse(BaseModel):
    issues: list[YouTrackIssue]


class KnowledgeDocumentSearchResponse(BaseModel):
    documents: list[YouTrackKnowledgeDocument]


def _client():
    try:
        return ensure_youtrack_available()
    except YouTrackConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/issues/{issue_id}", response_model=YouTrackIssue)
def get_issue(issue_id: str) -> YouTrackIssue:
    return _client().get_issue(issue_id)


@router.get("/issues", response_model=IssueSearchResponse)
def search_issues(project: str, query: str | None = None, limit: int = 20) -> IssueSearchResponse:
    return IssueSearchResponse(
        issues=_client().search_issues(project=project, query=query, limit=limit)
    )


@router.post("/issues", response_model=YouTrackIssue)
def create_issue(request: YouTrackIssueCreatePayload) -> YouTrackIssue:
    return _client().create_issue(request)


@router.post("/issues/{issue_id}", response_model=YouTrackIssue)
def update_issue(issue_id: str, request: YouTrackIssueUpdatePayload) -> YouTrackIssue:
    return _client().update_issue(issue_id, request)


@router.post("/issues/{issue_id}/comments", response_model=YouTrackComment)
def add_issue_comment(issue_id: str, request: YouTrackCommentPayload) -> YouTrackComment:
    return _client().add_comment(issue_id, request)


@router.get("/articles", response_model=KnowledgeDocumentSearchResponse)
def list_knowledge_documents(
    project: str,
    query: str | None = None,
    limit: int = 20,
) -> KnowledgeDocumentSearchResponse:
    return KnowledgeDocumentSearchResponse(
        documents=_client().list_knowledge_documents(
            project=project,
            query=query,
            limit=limit,
        )
    )


@router.get("/articles/{document_id}", response_model=YouTrackKnowledgeDocument)
def get_knowledge_document(document_id: str) -> YouTrackKnowledgeDocument:
    return _client().get_knowledge_document(document_id)


@router.post("/articles", response_model=YouTrackKnowledgeDocument)
def create_knowledge_document(
    request: YouTrackKnowledgeDocumentUpsertPayload,
) -> YouTrackKnowledgeDocument:
    return _client().upsert_knowledge_document(request)


@router.post("/articles/{document_id}", response_model=YouTrackKnowledgeDocument)
def update_knowledge_document(
    document_id: str,
    request: YouTrackKnowledgeDocumentUpsertPayload,
) -> YouTrackKnowledgeDocument:
    request_with_id = request.model_copy(update={"document_id": document_id})
    return _client().upsert_knowledge_document(request_with_id)


@router.get("/context/{role}", response_model=AgentContextBundle)
def get_agent_context_bundle(
    role: str,
    project: str,
    issue_id: str | None = None,
    issue_query: str | None = None,
) -> AgentContextBundle:
    return _client().get_agent_context(
        project=project,
        role=role,
        issue_id=issue_id,
        issue_query=issue_query,
    )
