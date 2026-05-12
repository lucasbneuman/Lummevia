from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from lummevia_memory import (
    MemoryCategory,
    ProjectMemoryRecord,
    ProjectMemoryRegistry,
    get_project_context,
)


router = APIRouter(prefix="/memory", tags=["memory"])


class ProjectContextResponse(BaseModel):
    project: str
    project_memories: list[dict[str, Any]]
    recent_decisions: list[dict[str, Any]]
    recent_qa_issues: list[dict[str, Any]]
    prompt_learnings: list[dict[str, Any]]
    qa_learnings: list[dict[str, Any]]
    recent_reviews: list[dict[str, Any]]
    project_memory_count: int


def _get_memory_registry() -> ProjectMemoryRegistry:
    return ProjectMemoryRegistry.default()


@router.get("/projects/{project}", response_model=ProjectContextResponse)
def get_memory_project_context(project: str) -> ProjectContextResponse:
    return ProjectContextResponse.model_validate(get_project_context(project))


@router.get("/projects/{project}/category/{category}", response_model=list[ProjectMemoryRecord])
def list_memories_by_category(
    project: str,
    category: MemoryCategory,
) -> list[ProjectMemoryRecord]:
    return _get_memory_registry().search_by_category(project, category)


@router.get("/projects/{project}/tags/{tag}", response_model=list[ProjectMemoryRecord])
def list_memories_by_tag(project: str, tag: str) -> list[ProjectMemoryRecord]:
    return _get_memory_registry().search_by_tag(project, tag)
