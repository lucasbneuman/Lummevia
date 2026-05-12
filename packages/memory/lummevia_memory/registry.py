from __future__ import annotations

from collections.abc import Iterable
from typing import Any, ClassVar

from lummevia_memory.schemas import (
    MemoryCategory,
    MemorySourceType,
    ProjectMemoryRecord,
)


class ProjectMemoryRegistry:
    _default_instance: ClassVar["ProjectMemoryRegistry" | None] = None

    def __init__(self) -> None:
        self._records: dict[str, ProjectMemoryRecord] = {}

    @classmethod
    def default(cls) -> "ProjectMemoryRegistry":
        if cls._default_instance is None:
            cls._default_instance = cls()
        return cls._default_instance

    def reset(self) -> None:
        self._records.clear()

    def add_memory(
        self,
        *,
        project: str,
        category: MemoryCategory,
        title: str,
        content: str,
        source_type: MemorySourceType,
        source_id: str,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProjectMemoryRecord:
        record = ProjectMemoryRecord(
            project=project,
            category=category,
            title=title,
            content=content,
            source_type=source_type,
            source_id=source_id,
            tags=tags or [],
            metadata=metadata or {},
        )
        self._records[record.memory_id] = record
        return record

    def get_memory(self, memory_id: str) -> ProjectMemoryRecord | None:
        return self._records.get(memory_id)

    def list_project_memories(self, project: str) -> list[ProjectMemoryRecord]:
        return sorted(
            (
                record
                for record in self._records.values()
                if record.project == project
            ),
            key=lambda record: record.created_at,
            reverse=True,
        )

    def search_by_tag(self, project: str, tag: str) -> list[ProjectMemoryRecord]:
        normalized_tag = tag.casefold()
        return [
            record
            for record in self.list_project_memories(project)
            if any(existing_tag.casefold() == normalized_tag for existing_tag in record.tags)
        ]

    def search_by_category(
        self,
        project: str,
        category: MemoryCategory,
    ) -> list[ProjectMemoryRecord]:
        return [
            record
            for record in self.list_project_memories(project)
            if record.category == category
        ]


def _truncate_content(content: str, *, limit: int = 180) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _summarize_records(
    records: Iterable[ProjectMemoryRecord],
) -> list[dict[str, Any]]:
    return [
        {
            "memory_id": record.memory_id,
            "category": record.category.value,
            "title": record.title,
            "content_preview": _truncate_content(record.content),
            "source_type": record.source_type.value,
            "source_id": record.source_id,
            "tags": record.tags,
            "created_at": record.created_at,
        }
        for record in records
    ]


def get_project_context(
    project: str,
    *,
    registry: ProjectMemoryRegistry | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    active_registry = registry or ProjectMemoryRegistry.default()
    project_memories = active_registry.list_project_memories(project)
    recent_decisions = active_registry.search_by_category(
        project,
        MemoryCategory.BUSINESS_DECISION,
    )[:limit]
    recent_qa_issues = active_registry.search_by_category(
        project,
        MemoryCategory.QA_ISSUE,
    )[:limit]
    prompt_learnings = active_registry.search_by_category(
        project,
        MemoryCategory.PROMPT_LEARNING,
    )[:limit]
    recent_reviews = active_registry.search_by_category(
        project,
        MemoryCategory.REVIEW_DECISION,
    )[:limit]

    return {
        "project": project,
        "project_memories": _summarize_records(project_memories[:limit]),
        "recent_decisions": _summarize_records(recent_decisions),
        "recent_qa_issues": _summarize_records(recent_qa_issues),
        "prompt_learnings": _summarize_records(prompt_learnings),
        "qa_learnings": _summarize_records(recent_qa_issues),
        "recent_reviews": _summarize_records(recent_reviews),
        "project_memory_count": len(project_memories),
    }


def build_project_memory_metadata(
    project: str,
    *,
    created_records: Iterable[ProjectMemoryRecord] | None = None,
    registry: ProjectMemoryRegistry | None = None,
) -> dict[str, Any]:
    active_registry = registry or ProjectMemoryRegistry.default()
    project_records = active_registry.list_project_memories(project)
    created = list(created_records or [])
    created_count = len(created) if created_records is not None else len(project_records)
    categories = sorted({record.category.value for record in project_records})
    return {
        "memory_records_created": created_count,
        "memory_categories": categories,
        "project_memory_count": len(project_records),
    }
