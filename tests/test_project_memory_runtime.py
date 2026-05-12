from lummevia_memory import MemoryCategory, ProjectMemoryRegistry
from lummevia_runtime import DevelopmentRuntime


def test_runtime_creates_project_memories_across_founder_qa_reviews_and_sessions() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-950")
    records = ProjectMemoryRegistry.default().list_project_memories("lummevia-os")
    categories = {record.category for record in records}

    assert state.metadata["project_memory_count"] == len(records)
    assert MemoryCategory.BUSINESS_DECISION in categories
    assert MemoryCategory.QA_ISSUE in categories
    assert MemoryCategory.REVIEW_DECISION in categories
    assert MemoryCategory.TASK_LEARNING in categories


def test_founder_conversation_generates_business_decision_memory() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-951")
    decision_memories = ProjectMemoryRegistry.default().search_by_category(
        "lummevia-os",
        MemoryCategory.BUSINESS_DECISION,
    )

    assert decision_memories
    assert decision_memories[0].source_type.value == "CONVERSATION"
    assert decision_memories[0].source_id == state.metadata["thread_id"]


def test_qa_fail_generates_qa_issue_memory() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-952")
    qa_issue_memories = ProjectMemoryRegistry.default().search_by_category(
        "lummevia-os",
        MemoryCategory.QA_ISSUE,
    )

    assert qa_issue_memories
    assert qa_issue_memories[0].title.startswith("QA issue")
    assert qa_issue_memories[0].metadata["task_id"] == state.artifacts.current_task_package.task_id


def test_pm_pipeline_consumes_project_context() -> None:
    runtime = DevelopmentRuntime()

    state = runtime.start_run(project="lummevia-os", issue_id="OS-953")
    pm_context = state.metadata["project_context"]["pm_business_brief"]
    pm_metadata = state.metadata["prompt_pipeline"]["pm_business_brief"]

    assert pm_context["recent_decisions"]
    assert pm_context["project_memory_count"] >= 1
    assert pm_metadata["project_memory_count"] >= 1
    assert pm_metadata["recent_decision_count"] >= 1
