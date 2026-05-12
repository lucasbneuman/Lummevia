from lummevia_memory import (
    MemoryCategory,
    MemorySourceType,
    ProjectMemoryRegistry,
    get_project_context,
)


def test_memory_registry_adds_and_gets_project_memory() -> None:
    registry = ProjectMemoryRegistry()

    record = registry.add_memory(
        project="lummevia-os",
        category=MemoryCategory.BUSINESS_DECISION,
        title="Founder narrowed the first iteration",
        content="Ship a smaller first iteration before expanding the scope.",
        source_type=MemorySourceType.CONVERSATION,
        source_id="thread-001",
        tags=["founder", "pm"],
        metadata={"issue_id": "OS-100"},
    )

    assert record.memory_id.startswith("memory-")
    assert registry.get_memory(record.memory_id) == record
    assert registry.list_project_memories("lummevia-os") == [record]


def test_memory_registry_searches_by_category_and_tag() -> None:
    registry = ProjectMemoryRegistry()
    business_memory = registry.add_memory(
        project="lummevia-os",
        category=MemoryCategory.BUSINESS_DECISION,
        title="Business decision",
        content="Keep the PM brief focused on retention.",
        source_type=MemorySourceType.CONVERSATION,
        source_id="thread-002",
        tags=["retention", "founder"],
    )
    qa_memory = registry.add_memory(
        project="lummevia-os",
        category=MemoryCategory.QA_ISSUE,
        title="QA issue",
        content="Validation failed on edge case coverage.",
        source_type=MemorySourceType.REVIEW,
        source_id="review-001",
        tags=["qa", "edge-case"],
    )

    assert registry.search_by_category(
        "lummevia-os",
        MemoryCategory.BUSINESS_DECISION,
    ) == [business_memory]
    assert registry.search_by_tag("lummevia-os", "qa") == [qa_memory]


def test_get_project_context_groups_recent_project_memories() -> None:
    registry = ProjectMemoryRegistry()
    registry.add_memory(
        project="lummevia-os",
        category=MemoryCategory.BUSINESS_DECISION,
        title="Decision",
        content="Keep PM and PO handoffs small and traceable.",
        source_type=MemorySourceType.CONVERSATION,
        source_id="thread-003",
        tags=["pm"],
    )
    registry.add_memory(
        project="lummevia-os",
        category=MemoryCategory.QA_ISSUE,
        title="QA issue",
        content="Regression on validation feedback formatting.",
        source_type=MemorySourceType.REVIEW,
        source_id="review-003",
        tags=["qa"],
    )
    registry.add_memory(
        project="lummevia-os",
        category=MemoryCategory.PROMPT_LEARNING,
        title="Prompt learning",
        content="Promotion accepted when latency delta stays under threshold.",
        source_type=MemorySourceType.WORKFLOW,
        source_id="regr-001",
        tags=["prompt"],
    )

    context = get_project_context("lummevia-os", registry=registry)

    assert context["project"] == "lummevia-os"
    assert context["project_memory_count"] == 3
    assert context["recent_decisions"][0]["category"] == "BUSINESS_DECISION"
    assert context["recent_qa_issues"][0]["category"] == "QA_ISSUE"
    assert context["prompt_learnings"][0]["category"] == "PROMPT_LEARNING"
    assert context["qa_learnings"][0]["category"] == "QA_ISSUE"
