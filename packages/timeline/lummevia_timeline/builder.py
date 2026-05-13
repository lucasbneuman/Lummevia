from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from lummevia_conversations import AuthorType, ConversationRegistry, ConversationThread
from lummevia_core import WorkflowRunEvent
from lummevia_memory import ProjectMemoryRecord, ProjectMemoryRegistry
from lummevia_reviews import (
    HumanReview,
    HumanReviewRegistry,
    ReviewDecision,
    ReviewStatus,
    ReviewType,
)
from lummevia_sessions import SessionEvent, SessionRegistry, TaskExecutionSession
from lummevia_timeline.registry import TimelineRegistry
from lummevia_timeline.schemas import TimelineEvent, TimelineSourceType, WorkflowTimeline


def build_workflow_timeline(
    state=None,
    *,
    workflow_run_id: str | None = None,
    project: str | None = None,
    issue_id: str | None = None,
    workflow_events: Iterable[WorkflowRunEvent] | None = None,
    conversations: Iterable[ConversationThread] | None = None,
    sessions: Iterable[TaskExecutionSession] | None = None,
    reviews: Iterable[HumanReview] | None = None,
    memory_records: Iterable[ProjectMemoryRecord] | None = None,
) -> WorkflowTimeline:
    run_id = workflow_run_id or (state.run.run_id if state is not None else None)
    resolved_project = project or (state.run.project if state is not None else None)
    resolved_issue_id = issue_id or (state.run.issue_id if state is not None else None)
    if run_id is None or resolved_project is None or resolved_issue_id is None:
        raise ValueError("workflow_run_id, project and issue_id are required to build a timeline.")

    resolved_workflow_events = list(
        workflow_events
        if workflow_events is not None
        else (state.run.events if state is not None else [])
    )
    resolved_conversations = list(
        conversations
        if conversations is not None
        else _resolve_conversations(
            run_id,
            resolved_project,
            resolved_issue_id,
            state=state,
        )
    )
    resolved_sessions = list(
        sessions
        if sessions is not None
        else _resolve_sessions(
            run_id,
            resolved_project,
            resolved_issue_id,
            state=state,
        )
    )
    resolved_reviews = list(
        reviews
        if reviews is not None
        else _resolve_reviews(
            run_id,
            resolved_project,
            resolved_issue_id,
            state=state,
        )
    )
    resolved_memory_records = list(
        memory_records
        if memory_records is not None
        else _resolve_memory_records(
            run_id,
            resolved_project,
            resolved_issue_id,
            state=state,
            reviews=resolved_reviews,
            sessions=resolved_sessions,
        )
    )

    events = [
        *list(_build_workflow_events(run_id, resolved_workflow_events)),
        *list(_build_conversation_events(run_id, resolved_conversations)),
        *list(_build_session_events(run_id, resolved_sessions)),
        *list(_build_review_events(run_id, resolved_reviews)),
        *list(_build_memory_events(run_id, resolved_memory_records)),
        *list(_build_system_events(run_id, state=state)),
    ]
    ordered_events = sorted(
        events,
        key=lambda event: (event.created_at, _event_sort_priority(event.event_type), event.event_id),
    )
    source_names = sorted({event.source_type.value for event in ordered_events})
    timeline_created_at = (
        ordered_events[0].created_at if ordered_events else datetime.now(UTC)
    )
    return WorkflowTimeline(
        workflow_run_id=run_id,
        project=resolved_project,
        issue_id=resolved_issue_id,
        created_at=timeline_created_at,
        events=ordered_events,
        metadata={
            "timeline_event_count": len(ordered_events),
            "timeline_sources": source_names,
            "replay_available": True,
        },
    )


def register_workflow_timeline(timeline: WorkflowTimeline) -> WorkflowTimeline:
    registry = TimelineRegistry.default()
    registry.create_timeline(
        workflow_run_id=timeline.workflow_run_id,
        project=timeline.project,
        issue_id=timeline.issue_id,
        metadata=timeline.metadata,
    )
    for event in timeline.events:
        registry.add_event(timeline.workflow_run_id, event)
    stored_timeline = registry.get_timeline(timeline.workflow_run_id)
    if stored_timeline is None:
        raise ValueError(f"Timeline '{timeline.workflow_run_id}' could not be registered.")
    updated_timeline = stored_timeline.model_copy(update={"metadata": timeline.metadata})
    registry._timelines[timeline.workflow_run_id] = updated_timeline
    return updated_timeline


def _resolve_conversations(
    workflow_run_id: str,
    project: str,
    issue_id: str,
    *,
    state=None,
) -> list[ConversationThread]:
    thread_ids = set()
    if state is not None:
        thread_id = str(state.metadata.get("thread_id", "")).strip()
        if thread_id:
            thread_ids.add(thread_id)
        thread_snapshot = state.metadata.get("conversation_thread")
        if isinstance(thread_snapshot, dict) and thread_snapshot.get("thread_id"):
            try:
                return [ConversationThread.model_validate(thread_snapshot)]
            except Exception:
                pass

    return [
        thread
        for thread in ConversationRegistry.default().list_threads()
        if thread.project == project
        and thread.issue_id == issue_id
        and (
            thread.metadata.get("run_id") == workflow_run_id
            or thread.thread_id in thread_ids
        )
    ]


def _resolve_sessions(
    workflow_run_id: str,
    project: str,
    issue_id: str,
    *,
    state=None,
) -> list[TaskExecutionSession]:
    registry_sessions = [
        session
        for session in SessionRegistry.default().list_sessions()
        if session.project == project
        and session.issue_id == issue_id
        and session.metadata.get("run_id") == workflow_run_id
    ]
    if registry_sessions:
        return registry_sessions
    if state is None:
        return []
    session_snapshots = state.metadata.get("sessions", {})
    if not isinstance(session_snapshots, dict):
        return []
    return [
        TaskExecutionSession.model_validate(snapshot)
        for snapshot in session_snapshots.values()
    ]


def _resolve_reviews(
    workflow_run_id: str,
    project: str,
    issue_id: str,
    *,
    state=None,
) -> list[HumanReview]:
    review_ids = set()
    snapshot_reviews: list[HumanReview] = []
    if state is not None:
        review_by_step = state.metadata.get("review_by_step", {})
        if isinstance(review_by_step, dict):
            for payload in review_by_step.values():
                if isinstance(payload, dict) and payload.get("review_id"):
                    review_ids.add(payload["review_id"])
                    snapshot_reviews.append(
                        _review_from_snapshot(
                            payload,
                            project=project,
                            issue_id=issue_id,
                        )
                    )
    registry_reviews = [
        review
        for review in HumanReviewRegistry.default().list_reviews()
        if (
            review.metadata.get("project") == project
            and review.metadata.get("issue_id") == issue_id
            and (
                review.metadata.get("run_id") == workflow_run_id
                or review.review_id in review_ids
            )
        )
    ]
    if registry_reviews:
        return registry_reviews
    return snapshot_reviews


def _resolve_memory_records(
    workflow_run_id: str,
    project: str,
    issue_id: str,
    *,
    state=None,
    reviews: Iterable[HumanReview],
    sessions: Iterable[TaskExecutionSession],
) -> list[ProjectMemoryRecord]:
    review_ids = {review.review_id for review in reviews}
    session_ids = {session.session_id for session in sessions}
    memory_ids = set()
    if state is not None:
        for memory_id in state.metadata.get("memory_record_ids", []):
            memory_ids.add(memory_id)
    return [
        record
        for record in ProjectMemoryRegistry.default().list_project_memories(project)
        if record.metadata.get("issue_id") == issue_id
        and (
            record.metadata.get("run_id") == workflow_run_id
            or record.memory_id in memory_ids
            or record.source_id in review_ids
            or record.source_id in session_ids
        )
    ]


def _build_workflow_events(
    workflow_run_id: str,
    workflow_events: Iterable[WorkflowRunEvent],
) -> Iterable[TimelineEvent]:
    for event in workflow_events:
        event_type = str(event.metadata.get("type", "WORKFLOW_EVENT"))
        yield TimelineEvent(
            event_id=event.event_id,
            workflow_run_id=workflow_run_id,
            event_type=event_type,
            source_type=TimelineSourceType.WORKFLOW,
            source_id=event.step_name,
            title=f"Workflow step {event.step_name}",
            description=event.message,
            created_at=event.created_at,
            metadata={
                "step_name": event.step_name,
                "status": event.status.value,
                **event.metadata,
            },
        )


def _build_conversation_events(
    workflow_run_id: str,
    conversations: Iterable[ConversationThread],
) -> Iterable[TimelineEvent]:
    for thread in conversations:
        for message in thread.messages:
            event_type = _conversation_message_event_type(message.author_type)
            yield TimelineEvent(
                event_id=message.message_id,
                workflow_run_id=workflow_run_id,
                event_type=event_type,
                source_type=TimelineSourceType.CONVERSATION,
                source_id=thread.thread_id,
                title=f"Conversation message in {thread.thread_id}",
                description=message.content,
                created_at=message.created_at,
                metadata={
                    "thread_id": thread.thread_id,
                    "author_type": message.author_type.value,
                    "role": message.role,
                    **message.metadata,
                },
            )
        yield TimelineEvent(
            event_id=f"{thread.thread_id}-status",
            workflow_run_id=workflow_run_id,
            event_type="CONVERSATION_STATUS_UPDATED",
            source_type=TimelineSourceType.CONVERSATION,
            source_id=thread.thread_id,
            title=f"Conversation status for {thread.thread_id}",
            description=f"Conversation thread is {thread.status.value}.",
            created_at=thread.updated_at,
            metadata={
                "thread_id": thread.thread_id,
                "conversation_status": thread.status.value,
                **thread.metadata,
            },
        )


def _build_session_events(
    workflow_run_id: str,
    sessions: Iterable[TaskExecutionSession],
) -> Iterable[TimelineEvent]:
    for session in sessions:
        yield TimelineEvent(
            event_id=f"{session.session_id}-started",
            workflow_run_id=workflow_run_id,
            event_type="SESSION_LIFECYCLE_STARTED",
            source_type=TimelineSourceType.SESSION,
            source_id=session.session_id,
            title=f"Session {session.session_id} started",
            description=f"Task session started for {session.task_id}.",
            created_at=session.started_at,
            metadata={
                "session_id": session.session_id,
                "task_id": session.task_id,
                "role": session.role.value,
                "mode": session.mode.value,
                "status": session.status.value,
            },
        )
        for event in sorted(session.events, key=lambda session_event: session_event.created_at):
            yield _build_session_event(workflow_run_id, session, event)
        for output in sorted(session.outputs, key=lambda session_output: session_output.created_at):
            yield TimelineEvent(
                event_id=output.output_id,
                workflow_run_id=workflow_run_id,
                event_type="SESSION_OUTPUT_RECORDED",
                source_type=TimelineSourceType.SESSION,
                source_id=session.session_id,
                title=f"Session output for {session.task_id}",
                description=output.content,
                created_at=output.created_at,
                metadata={
                    "session_id": session.session_id,
                    "task_id": session.task_id,
                    "output_type": output.output_type,
                    **output.metadata,
                },
            )
        if session.completed_at is not None:
            yield TimelineEvent(
                event_id=f"{session.session_id}-completed",
                workflow_run_id=workflow_run_id,
                event_type="SESSION_LIFECYCLE_COMPLETED",
                source_type=TimelineSourceType.SESSION,
                source_id=session.session_id,
                title=f"Session {session.session_id} completed",
                description=f"Task session finished with status {session.status.value}.",
                created_at=session.completed_at,
                metadata={
                    "session_id": session.session_id,
                    "task_id": session.task_id,
                    "status": session.status.value,
                    "attempts": session.attempts,
                },
            )


def _build_review_events(
    workflow_run_id: str,
    reviews: Iterable[HumanReview],
) -> Iterable[TimelineEvent]:
    for review in reviews:
        yield TimelineEvent(
            event_id=f"{review.review_id}-created",
            workflow_run_id=workflow_run_id,
            event_type=_review_created_event_type(review),
            source_type=TimelineSourceType.REVIEW,
            source_id=review.review_id,
            title=f"Review {review.review_id} created",
            description=f"{review.review_type.value} review created for {review.target_id}.",
            created_at=review.created_at,
            metadata={
                "review_id": review.review_id,
                "review_type": review.review_type.value,
                "review_status": review.status.value,
                "target_id": review.target_id,
                "target_type": review.target_type,
            },
        )
        if review.status.value == "COMPLETED":
            yield TimelineEvent(
                event_id=f"{review.review_id}-completed",
                workflow_run_id=workflow_run_id,
                event_type="REVIEW_COMPLETED",
                source_type=TimelineSourceType.REVIEW,
                source_id=review.review_id,
                title=f"Review {review.review_id} completed",
                description=(
                    f"{review.review_type.value} review completed with "
                    f"{review.decision.value if review.decision is not None else 'UNKNOWN'}."
                ),
                created_at=review.updated_at,
                metadata={
                    "review_id": review.review_id,
                    "review_type": review.review_type.value,
                    "review_status": review.status.value,
                    "review_decision": (
                        review.decision.value if review.decision is not None else None
                    ),
                    "target_id": review.target_id,
                    "target_type": review.target_type,
                },
            )


def _build_memory_events(
    workflow_run_id: str,
    memory_records: Iterable[ProjectMemoryRecord],
) -> Iterable[TimelineEvent]:
    for record in memory_records:
        yield TimelineEvent(
            event_id=record.memory_id,
            workflow_run_id=workflow_run_id,
            event_type="MEMORY_RECORDED",
            source_type=TimelineSourceType.MEMORY,
            source_id=record.source_id,
            title=record.title,
            description=record.content,
            created_at=record.created_at,
            metadata={
                "memory_id": record.memory_id,
                "memory_category": record.category.value,
                "memory_source_type": record.source_type.value,
                "tags": record.tags,
                **record.metadata,
            },
            )


def _build_system_events(
    workflow_run_id: str,
    *,
    state=None,
) -> Iterable[TimelineEvent]:
    if state is None:
        return []
    events: list[TimelineEvent] = []
    queue_events = state.metadata.get("queue_events", [])
    if isinstance(queue_events, list):
        for raw_event in queue_events:
            if not isinstance(raw_event, dict):
                continue
            metadata = raw_event.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            events.append(
                TimelineEvent(
                    event_id=str(raw_event.get("event_id", "")),
                    workflow_run_id=workflow_run_id,
                    event_type=str(raw_event.get("event_type", "SYSTEM_EVENT")),
                    source_type=TimelineSourceType.SYSTEM,
                    source_id=str(metadata.get("queue_id", "task_queue")),
                    title=str(raw_event.get("title", "System event")),
                    description=str(raw_event.get("description", "System event recorded.")),
                    created_at=raw_event.get("created_at"),
                    metadata=metadata,
                )
            )
    supervisor_events = state.metadata.get("supervisor_events", [])
    if not isinstance(supervisor_events, list):
        supervisor_events = []
    for raw_event in supervisor_events:
        if not isinstance(raw_event, dict):
            continue
        metadata = raw_event.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        events.append(
            TimelineEvent(
                event_id=str(raw_event.get("event_id", "")),
                workflow_run_id=workflow_run_id,
                event_type=str(raw_event.get("event_type", "SUPERVISOR_EVENT")),
                source_type=TimelineSourceType.SYSTEM,
                source_id=str(
                    metadata.get("queue_item_id")
                    or metadata.get("session_id")
                    or metadata.get("watchdog_id")
                    or "supervisor"
                ),
                title=str(raw_event.get("event_type", "Supervisor event")),
                description=str(
                    metadata.get("reason")
                    or metadata.get("action_type")
                    or raw_event.get("event_type", "Supervisor event recorded.")
                ),
                created_at=raw_event.get("created_at"),
                metadata={
                    **metadata,
                    "status": raw_event.get("status"),
                },
            )
        )
    decision_events = state.metadata.get("execution_decisions", [])
    if isinstance(decision_events, list):
        for raw_decision in decision_events:
            if not isinstance(raw_decision, dict):
                continue
            metadata = raw_decision.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            decision_status = str(raw_decision.get("status", "PROPOSED"))
            events.append(
                TimelineEvent(
                    event_id=str(raw_decision.get("decision_id", "")),
                    workflow_run_id=workflow_run_id,
                    event_type=f"DECISION_{decision_status}",
                    source_type=TimelineSourceType.SYSTEM,
                    source_id=str(raw_decision.get("decision_id", "execution_decision")),
                    title=f"Decision {raw_decision.get('decision_type', 'UNKNOWN')}",
                    description=str(raw_decision.get("reason", "Execution decision recorded.")),
                    created_at=raw_decision.get("created_at"),
                    metadata={
                        "decision_id": raw_decision.get("decision_id"),
                        "decision_type": raw_decision.get("decision_type"),
                        "decision_status": decision_status,
                        "recommended_action": raw_decision.get("recommended_action"),
                        "requires_human_review": raw_decision.get("requires_human_review"),
                        **metadata,
                    },
                )
            )
    strategy_events = state.metadata.get("execution_strategies", [])
    if isinstance(strategy_events, list):
        for raw_strategy in strategy_events:
            if not isinstance(raw_strategy, dict):
                continue
            metadata = raw_strategy.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            events.append(
                TimelineEvent(
                    event_id=str(raw_strategy.get("strategy_id", "")),
                    workflow_run_id=workflow_run_id,
                    event_type=str(metadata.get("strategy_event", "STRATEGY_SELECTED")),
                    source_type=TimelineSourceType.SYSTEM,
                    source_id=str(raw_strategy.get("strategy_id", "execution_strategy")),
                    title=f"Strategy {raw_strategy.get('strategy_type', 'UNKNOWN')}",
                    description=str(raw_strategy.get("reasoning", "Execution strategy recorded.")),
                    created_at=raw_strategy.get("created_at"),
                    metadata={
                        "strategy_id": raw_strategy.get("strategy_id"),
                        "strategy_type": raw_strategy.get("strategy_type"),
                        "risk_level": raw_strategy.get("risk_level"),
                        "qa_level": raw_strategy.get("qa_level"),
                        "sandbox_level": raw_strategy.get("sandbox_level"),
                        "selected_model": raw_strategy.get("selected_model"),
                        "selected_provider": raw_strategy.get("selected_provider"),
                        "execution_mode": raw_strategy.get("execution_mode"),
                        **metadata,
                    },
                )
            )
    adaptive_plans = state.metadata.get("adaptive_plans", [])
    if not isinstance(adaptive_plans, list):
        return events
    for raw_plan in adaptive_plans:
        if not isinstance(raw_plan, dict):
            continue
        plan_metadata = raw_plan.get("metadata", {})
        if not isinstance(plan_metadata, dict):
            plan_metadata = {}
        plan_id = str(raw_plan.get("adaptive_plan_id", "adaptive_plan"))
        created_at = raw_plan.get("created_at")
        events.append(
            TimelineEvent(
                event_id=f"{plan_id}-created",
                workflow_run_id=workflow_run_id,
                event_type="ADAPTIVE_PLAN_CREATED",
                source_type=TimelineSourceType.SYSTEM,
                source_id=plan_id,
                title=f"Adaptive plan {plan_id} created",
                description=str(raw_plan.get("trigger_reason", "Adaptive plan created.")),
                created_at=created_at,
                metadata={
                    "adaptive_plan_id": plan_id,
                    "adaptive_plan_status": raw_plan.get("status"),
                    "source_task_id": raw_plan.get("source_task_id"),
                    **plan_metadata,
                },
            )
        )
        mutation_event_type = _mutation_event_type(str(raw_plan.get("status", "PROPOSED")))
        mutation_created_at = raw_plan.get("updated_at") or created_at
        for raw_mutation in raw_plan.get("mutations", []):
            if not isinstance(raw_mutation, dict):
                continue
            mutation_metadata = raw_mutation.get("metadata", {})
            if not isinstance(mutation_metadata, dict):
                mutation_metadata = {}
            events.append(
                TimelineEvent(
                    event_id=str(raw_mutation.get("mutation_id", "")),
                    workflow_run_id=workflow_run_id,
                    event_type=mutation_event_type,
                    source_type=TimelineSourceType.SYSTEM,
                    source_id=plan_id,
                    title=f"Graph mutation {raw_mutation.get('mutation_type', 'UNKNOWN')}",
                    description=str(raw_mutation.get("reason", "Graph mutation proposed.")),
                    created_at=mutation_created_at,
                    metadata={
                        "adaptive_plan_id": plan_id,
                        "adaptive_plan_status": raw_plan.get("status"),
                        "mutation_id": raw_mutation.get("mutation_id"),
                        "mutation_type": raw_mutation.get("mutation_type"),
                        "target": raw_mutation.get("target"),
                        **mutation_metadata,
                    },
                )
            )
    return events


def _build_session_event(
    workflow_run_id: str,
    session: TaskExecutionSession,
    event: SessionEvent,
) -> TimelineEvent:
    event_type = "SESSION_STATUS_UPDATED" if event.type == "STATUS_UPDATED" else event.type
    return TimelineEvent(
        event_id=event.event_id,
        workflow_run_id=workflow_run_id,
        event_type=event_type,
        source_type=TimelineSourceType.SESSION,
        source_id=session.session_id,
        title=f"Session event for {session.task_id}",
        description=event.message,
        created_at=event.created_at,
        metadata={
            "session_id": session.session_id,
            "task_id": session.task_id,
            **event.metadata,
        },
    )


def _event_sort_priority(event_type: str) -> int:
    if event_type == "SESSION_LIFECYCLE_STARTED":
        return 0
    if event_type == "SESSION_LIFECYCLE_COMPLETED":
        return 2
    return 1


def _conversation_message_event_type(author_type: AuthorType) -> str:
    if author_type == AuthorType.FOUNDER:
        return "FOUNDER_CONVERSATION_MESSAGE"
    if author_type == AuthorType.PM:
        return "PM_CONVERSATION_MESSAGE"
    return "SYSTEM_CONVERSATION_MESSAGE"


def _review_created_event_type(review: HumanReview) -> str:
    if review.review_type == ReviewType.QA_VALIDATION:
        return "QA_REVIEW_PENDING"
    return "REVIEW_CREATED"


def _review_from_snapshot(
    payload: dict[str, Any],
    *,
    project: str,
    issue_id: str,
) -> HumanReview:
    review_type = ReviewType(payload.get("review_type", ReviewType.TASK_PLAN.value))
    review_status = ReviewStatus(payload.get("review_status", ReviewStatus.PENDING.value))
    review_decision = payload.get("review_decision")
    return HumanReview(
        review_id=str(payload["review_id"]),
        review_type=review_type,
        target_id=str(payload.get("target_id", issue_id)),
        target_type=str(payload.get("target_type", "WorkflowArtifact")),
        requested_by=str(payload.get("requested_by", "system")),
        assigned_to=payload.get("assigned_to"),
        status=review_status,
        decision=ReviewDecision(review_decision) if review_decision else None,
        notes=str(payload.get("notes", "")),
        metadata={
            "project": project,
            "issue_id": issue_id,
            **payload,
        },
    )


def _mutation_event_type(status: str) -> str:
    if status == "APPROVED":
        return "GRAPH_MUTATION_APPROVED"
    if status == "REJECTED":
        return "GRAPH_MUTATION_REJECTED"
    if status == "APPLIED":
        return "GRAPH_MUTATION_APPLIED"
    return "GRAPH_MUTATION_PROPOSED"
