from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class YouTrackBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class YouTrackIssueRef(YouTrackBaseSchema):
    issue_id: str = Field(min_length=1)
    project: str = Field(min_length=1)


class YouTrackCommentPayload(YouTrackBaseSchema):
    body: str = Field(min_length=1)


class YouTrackArtifactLink(YouTrackBaseSchema):
    artifact_type: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl | None = None


class YouTrackBugPayload(YouTrackBaseSchema):
    project: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    description: str = Field(min_length=1)
    related_issue_id: str | None = None
    steps_to_reproduce: list[str]
    expected_behavior: str | None = None
    actual_behavior: str | None = None
