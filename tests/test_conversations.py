from lummevia_conversations import (
    AuthorType,
    ConversationPhase,
    ConversationRegistry,
    ConversationStatus,
    apply_founder_message_policy,
    build_initial_founder_pm_state,
    is_explicit_approval,
    update_thread_with_policy_decision,
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


def test_founder_pm_policy_asks_questions_when_contract_is_incomplete() -> None:
    registry = ConversationRegistry()
    thread = registry.create_thread(
        topic="Founder strategic iteration",
        project="lummevia-os",
        issue_id="OS-304",
        founder_pm_state=build_initial_founder_pm_state(
            thread_id="seed-thread-id",
            project="lummevia-os",
            issue_id="OS-304",
            telegram_chat_id=7001,
        ),
    )
    thread = thread.model_copy(
        update={
            "founder_pm_state": build_initial_founder_pm_state(
                thread_id=thread.thread_id,
                project="lummevia-os",
                issue_id="OS-304",
                telegram_chat_id=7001,
            )
        }
    )

    decision = apply_founder_message_policy(
        thread,
        founder_message="crear app para reservas medicas",
    )

    assert decision.phase == ConversationPhase.PM_QUESTIONS
    assert decision.iteration_count == 1
    assert len(decision.pending_questions) == 3
    assert decision.pending_question_fields == ["constraints", "user", "scope"]


def test_founder_pm_policy_builds_draft_after_questions_are_answered() -> None:
    registry = ConversationRegistry()
    thread = registry.create_thread(
        topic="Founder strategic iteration",
        project="lummevia-os",
        issue_id="OS-305",
        founder_pm_state=build_initial_founder_pm_state(
            thread_id="seed-thread-id",
            project="lummevia-os",
            issue_id="OS-305",
            telegram_chat_id=7001,
        ),
    )
    thread = thread.model_copy(
        update={
            "founder_pm_state": build_initial_founder_pm_state(
                thread_id=thread.thread_id,
                project="lummevia-os",
                issue_id="OS-305",
                telegram_chat_id=7001,
            )
        }
    )

    first_decision = apply_founder_message_policy(
        thread,
        founder_message="crear app para reservas medicas",
    )
    thread = update_thread_with_policy_decision(thread, first_decision)
    thread = registry.save_thread(thread)
    thread = registry.add_message(
        thread.thread_id,
        role="assistant",
        author_type=AuthorType.PM,
        content=first_decision.last_pm_message or "",
        metadata={"conversation_event": "PM_QUESTION_SENT"},
    )

    second_decision = apply_founder_message_policy(
        thread,
        founder_message=(
            "1. Sin chatbot libre ni autoaprobacion.\n"
            "2. Lo usan recepcionistas y pacientes.\n"
            "3. MVP: crear reserva, confirmar turno y ver agenda.\n"
            "4. Exito: validar una reserva de punta a punta."
        ),
    )

    assert second_decision.phase == ConversationPhase.PENDING_APPROVAL
    assert second_decision.brief_version == 1
    assert second_decision.pending_questions == []
    assert second_decision.brief_draft is not None
    assert second_decision.brief_draft["conversation_thread_id"] == thread.thread_id
    assert second_decision.brief_draft["brief_version"] == 1


def test_founder_pm_policy_stops_after_five_iterations_and_forces_draft() -> None:
    state = build_initial_founder_pm_state(
        thread_id="thread-123",
        project="lummevia-os",
        issue_id="OS-306",
        telegram_chat_id=7001,
    ).model_copy(update={"iteration_count": 5, "metadata": {"contract_context": {}}})
    thread = ConversationRegistry().create_thread(
        topic="Founder strategic iteration",
        project="lummevia-os",
        issue_id="OS-306",
        founder_pm_state=state,
    )

    decision = apply_founder_message_policy(thread, founder_message="todavia no se")

    assert decision.phase == ConversationPhase.PENDING_APPROVAL
    assert decision.brief_draft is not None
    assert decision.metadata["max_iterations_reached"] is True


def test_explicit_approval_detection_is_deterministic() -> None:
    assert is_explicit_approval("approve") is True
    assert is_explicit_approval("ok aprobar") is True
    assert is_explicit_approval("confirmo") is True
    assert is_explicit_approval("sigamos iterando") is False
