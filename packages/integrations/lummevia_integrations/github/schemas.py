from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GitHubBaseSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class GitHubRepoRef(GitHubBaseSchema):
    owner: str = Field(min_length=1)
    name: str = Field(min_length=1)


class GitHubBranchRef(GitHubBaseSchema):
    repo: GitHubRepoRef
    branch: str = Field(min_length=1)


class GitHubCommitRef(GitHubBaseSchema):
    repo: GitHubRepoRef
    sha: str = Field(min_length=1)


class GitHubPullRequestRef(GitHubBaseSchema):
    repo: GitHubRepoRef
    pr_number: int = Field(gt=0)


class GitHubPullRequestPayload(GitHubBaseSchema):
    repo: GitHubRepoRef
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    head: str = Field(min_length=1)
    base: str = Field(min_length=1)
    draft: bool = False
