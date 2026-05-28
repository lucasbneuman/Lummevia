from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class YouTrackBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class YouTrackIssueRef(YouTrackBaseSchema):
    issue_id: str = Field(min_length=1)
    project: str = Field(min_length=1)


class YouTrackProject(YouTrackBaseSchema):
    id: str | None = None
    short_name: str = Field(min_length=1)
    name: str = Field(min_length=1)
    archived: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class YouTrackIssueCustomField(YouTrackBaseSchema):
    name: str = Field(min_length=1)
    value: Any = None


class YouTrackIssue(YouTrackIssueRef):
    id: str | None = None
    summary: str = Field(min_length=1)
    description: str | None = None
    state: str | None = None
    url: HttpUrl | None = None
    custom_fields: list[YouTrackIssueCustomField] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class YouTrackCommentPayload(YouTrackBaseSchema):
    body: str = Field(min_length=1)


class YouTrackComment(YouTrackBaseSchema):
    comment_id: str | None = None
    issue_id: str = Field(min_length=1)
    body: str = Field(min_length=1)
    url: HttpUrl | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class YouTrackArtifactLink(YouTrackBaseSchema):
    artifact_type: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl | None = None


class YouTrackIssueCreatePayload(YouTrackBaseSchema):
    project: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description: str = ""
    parent_issue_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class YouTrackIssueUpdatePayload(YouTrackBaseSchema):
    summary: str | None = None
    description: str | None = None
    state: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)


class YouTrackBugPayload(YouTrackBaseSchema):
    project: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description: str = Field(min_length=1)
    related_issue_id: str | None = None
    steps_to_reproduce: list[str]
    expected_behavior: str | None = None
    actual_behavior: str | None = None


class YouTrackKnowledgeDocument(YouTrackBaseSchema):
    document_id: str = Field(min_length=1)
    id_readable: str | None = None
    project: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str | None = None
    url: HttpUrl | None = None
    parent_document_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class YouTrackKnowledgeDocumentUpsertPayload(YouTrackBaseSchema):
    project: str = Field(min_length=1)
    title: str = Field(min_length=1)
    content: str = ""
    document_id: str | None = None
    parent_document_id: str | None = None
    tags: list[str] = Field(default_factory=list)


class ProjectContextSourceType(StrEnum):
    ISSUE = "ISSUE"
    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"


class ProjectContextSource(YouTrackBaseSchema):
    source_type: ProjectContextSourceType
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl | None = None
    required: bool = False
    role: str | None = None


class KnowledgeDocumentRef(YouTrackBaseSchema):
    document_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl | None = None
    summary: str | None = None


class OperationalIssueRef(YouTrackBaseSchema):
    issue_id: str = Field(min_length=1)
    project: str = Field(min_length=1)
    summary: str | None = None
    state: str | None = None
    url: HttpUrl | None = None


class AgentContextBundle(YouTrackBaseSchema):
    project: str = Field(min_length=1)
    role: str = Field(min_length=1)
    issue: OperationalIssueRef | None = None
    related_issues: list[OperationalIssueRef] = Field(default_factory=list)
    knowledge_documents: list[KnowledgeDocumentRef] = Field(default_factory=list)
    sources: list[ProjectContextSource] = Field(default_factory=list)
    artifact_links: list[YouTrackArtifactLink] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
