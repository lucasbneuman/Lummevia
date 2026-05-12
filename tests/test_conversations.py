from lummevia_conversations import (
    AuthorType,
    ConversationRegistry,
    ConversationStatus,
)


def test_conversation_registry_creates_and_lists_threads() -> None:
    registry = ConversationRegistry()

    created = registry.create_thread(
        topic="Founder strategic iteration",
        project="lummevia-os",
        issue_id="OS-301",
        metadata={"source": "runtime"},
    )

    assert created.thread_id
    assert created.status is ConversationStatus.ACTIVE
    assert created.project == "lummevia-os"
    assert created.issue_id == "OS-301"
    assert created.metadata["source"] == "runtime"
    assert registry.get_thread(created.thread_id) == created
    assert registry.list_threads() == [created]


def test_conversation_registry_adds_messages_and_updates_timestamp() -> None:
    registry = ConversationRegistry()
    thread = registry.create_thread(
        topic="Founder strategic iteration",
        project="lummevia-os",
        issue_id="OS-302",
    )
    original_updated_at = thread.updated_at

    updated = registry.add_message(
        thread.thread_id,
        role="user",
        author_type=AuthorType.FOUNDER,
        content="We should simplify the initial scope.",
        metadata={"iteration": 1},
    )

    assert len(updated.messages) == 1
    assert updated.messages[0].message_id
    assert updated.messages[0].author_type is AuthorType.FOUNDER
    assert updated.messages[0].content == "We should simplify the initial scope."
    assert updated.messages[0].metadata["iteration"] == 1
    assert updated.updated_at >= original_updated_at


def test_conversation_registry_can_approve_and_close_threads() -> None:
    registry = ConversationRegistry()
    thread = registry.create_thread(
        topic="Founder strategic iteration",
        project="lummevia-os",
        issue_id="OS-303",
    )

    approved = registry.update_thread_status(
        thread.thread_id,
        ConversationStatus.APPROVED,
        metadata={"business_brief_status": "approved"},
    )
    closed = registry.close_thread(thread.thread_id)

    assert approved.status is ConversationStatus.APPROVED
    assert approved.metadata["business_brief_status"] == "approved"
    assert closed.status is ConversationStatus.CLOSED
