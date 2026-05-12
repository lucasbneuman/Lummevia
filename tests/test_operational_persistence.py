from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes import runtime as runtime_routes
from app.core.persistence import (
    annotate_runtime_state,
    configure_operational_persistence,
    rehydrate_registries,
)
from lummevia_capabilities import AllocationRequest, CapabilityAllocator, CapabilityRegistry
from lummevia_conversations import AuthorType, ConversationRegistry
from lummevia_core import AgentRole
from lummevia_integrations import PhoenixClient, PhoenixRuntimeObserver
from lummevia_kilo import KiloExecutionMode
from lummevia_memory import MemoryCategory, MemorySourceType, ProjectMemoryRegistry
from lummevia_persistence import (
    OperationalPersistenceService,
    create_database_engine,
    create_session_factory,
    create_tables,
)
from lummevia_queue import TaskPriority, TaskQueueItem, TaskQueueRegistry, TaskQueueStatus
from lummevia_resources import ResourceRegistry, ResourceType, WorkspaceAllocation, WorkspaceStatus
from lummevia_reviews import HumanReviewRegistry, ReviewDecision, ReviewType
from lummevia_runtime import DevelopmentRuntime
from lummevia_runtime.persistence import (
    SqlAlchemyWorkflowRunRepository,
    create_database_engine as create_runtime_database_engine,
    create_session_factory as create_runtime_session_factory,
    create_tables as create_runtime_tables,
)
from lummevia_sessions import SessionRegistry, SessionStatus
from lummevia_supervisor import ExecutionHealthStatus, SupervisorRegistry
from lummevia_timeline import TimelineRegistry
from main import app


def _build_operational_service(tmp_path: Path) -> OperationalPersistenceService:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'operational.db'}")
    create_tables(engine)
    return OperationalPersistenceService(create_session_factory(engine))


def test_operational_persistence_rehydrates_after_simulated_restart(tmp_path: Path) -> None:
    service = _build_operational_service(tmp_path)
    configure_operational_persistence(service)

    queue = TaskQueueRegistry.default().create_queue(
        project="lummevia-os",
        workflow_run_id="run-001",
        metadata={"issue_id": "OS-801"},
    )
    queue_item = TaskQueueRegistry.default().add_item(
        queue.queue_id,
        TaskQueueItem(
            task_id="OS-801-T1",
            project="lummevia-os",
            issue_id="OS-801",
            priority=TaskPriority.HIGH,
            status=TaskQueueStatus.QUEUED,
            assigned_role=AgentRole.DEV,
            mode=KiloExecutionMode.CODE,
            metadata={"title": "Persist queue item"},
        ),
    )
    TaskQueueRegistry.default().update_item_status(
        queue.queue_id,
        queue_item.queue_item_id,
        TaskQueueStatus.RUNNING,
    )

    thread = ConversationRegistry.default().create_thread(
        topic="Persistence",
        project="lummevia-os",
        issue_id="OS-801",
        metadata={"run_id": "run-001"},
    )
    ConversationRegistry.default().add_message(
        thread.thread_id,
        role="founder",
        author_type=AuthorType.FOUNDER,
        content="Necesitamos persistencia real.",
    )

    review = HumanReviewRegistry.default().create_review(
        review_type=ReviewType.QA_VALIDATION,
        target_id="OS-801-T1",
        target_type="TaskPackage",
        requested_by="qa",
        metadata={"project": "lummevia-os", "issue_id": "OS-801", "run_id": "run-001"},
    )
    HumanReviewRegistry.default().complete_review(
        review.review_id,
        decision=ReviewDecision.APPROVED,
    )

    memory = ProjectMemoryRegistry.default().add_memory(
        project="lummevia-os",
        category=MemoryCategory.TASK_LEARNING,
        title="Persist memory",
        content="La memoria del proyecto ya queda durable.",
        source_type=MemorySourceType.SYSTEM,
        source_id="run-001",
        metadata={"issue_id": "OS-801", "run_id": "run-001"},
    )

    session = SessionRegistry.default().create_session(
        task_id="OS-801-T1",
        project="lummevia-os",
        issue_id="OS-801",
        role=AgentRole.DEV,
        mode=KiloExecutionMode.CODE,
        metadata={"run_id": "run-001"},
    )
    SessionRegistry.default().update_status(
        session.session_id,
        status=SessionStatus.COMPLETED,
        role=AgentRole.DEV,
        mode=KiloExecutionMode.CODE,
    )

    lock = ResourceRegistry.default().acquire_lock(
        resource_type=ResourceType.WORKSPACE,
        resource_id="workspace-001",
        owner_id="queue-item-001",
        owner_type="TaskQueueItem",
        metadata={"run_id": "run-001"},
    )
    workspace = ResourceRegistry.default().save_workspace(
        WorkspaceAllocation(
            workspace_id="workspace-001",
            project="lummevia-os",
            repo="lummevia-os",
            task_id="OS-801-T1",
            queue_item_id=queue_item.queue_item_id,
            branch_name="lummevia/lummevia-os/os-801-t1-001",
            worktree_path="/virtual/kilo-workspaces/lummevia-os/workspace-001",
            status=WorkspaceStatus.ACTIVE,
            metadata={"lock_ids": [lock.lock_id], "run_id": "run-001"},
        )
    )
    assert workspace.status == WorkspaceStatus.ACTIVE

    allocation = CapabilityAllocator.default().request_allocation(
        AllocationRequest(
            request_id="req-001",
            project="lummevia-os",
            issue_id="OS-801",
            task_id="OS-801-T1",
            role=AgentRole.DEV,
            mode=KiloExecutionMode.CODE,
            provider="DEEPSEEK",
            model="deepseek-v4-lite-placeholder",
            required_resources=[],
        )
    )
    assert allocation is not None

    watchdog = SupervisorRegistry.default().register_watchdog(
        workflow_run_id="run-001",
        target_type="TaskExecutionSession",
        target_id=session.session_id,
        metadata={"session_id": session.session_id},
    )
    SupervisorRegistry.default().create_supervisor_event(
        workflow_run_id="run-001",
        event_type="SESSION_PERSISTED",
        status=ExecutionHealthStatus.RUNNING,
        session_id=session.session_id,
    )
    dead_letter = SupervisorRegistry.default().mark_dead_letter(
        workflow_run_id="run-001",
        task_id="OS-801-T2",
        queue_item_id="queue-item-dead",
        reason="Retries exhausted",
    )

    assert memory.memory_id
    assert watchdog.watchdog_id
    assert dead_letter.dead_letter_id

    TaskQueueRegistry.default().reset()
    SessionRegistry.default().reset()
    SupervisorRegistry.default().reset()
    ProjectMemoryRegistry.default().reset()
    HumanReviewRegistry.default().reset()
    ConversationRegistry.default().reset()
    ResourceRegistry.default().reset()
    CapabilityRegistry.default().reset()
    TimelineRegistry.default().reset()

    configure_operational_persistence(service)
    results = rehydrate_registries()

    assert results["queues"]["status"] == "ok"
    assert results["sessions"]["status"] == "ok"
    assert results["supervisor"]["status"] == "ok"
    assert results["memory"]["status"] == "ok"
    assert results["reviews"]["status"] == "ok"
    assert results["conversations"]["status"] == "ok"
    assert results["resources"]["status"] == "ok"
    assert results["capabilities"]["status"] == "ok"
    assert TaskQueueRegistry.default().get_queue(queue.queue_id) is not None
    assert SessionRegistry.default().get_session(session.session_id) is not None
    assert any(item.dead_letter_id == dead_letter.dead_letter_id for item in SupervisorRegistry.default().list_dead_letters())
    assert ResourceRegistry.default().get_workspace("workspace-001") is not None
    assert ConversationRegistry.default().get_thread(thread.thread_id).messages
    assert HumanReviewRegistry.default().get_review(review.review_id) is not None
    assert ProjectMemoryRegistry.default().get_memory(memory.memory_id) is not None
    assert CapabilityRegistry.default().list_capacity()


def test_queue_persistence_failure_keeps_in_memory_state() -> None:
    class FailingQueuePersistence:
        def save_queue(self, queue):
            raise RuntimeError("postgres down")

    registry = TaskQueueRegistry.default()
    registry.configure_persistence(FailingQueuePersistence())

    queue = registry.create_queue(project="lummevia-os", workflow_run_id="run-002")

    assert registry.get_queue(queue.queue_id) is not None


def test_persistence_endpoints_and_timeline_rebuild_from_storage(tmp_path: Path) -> None:
    service = _build_operational_service(tmp_path)
    configure_operational_persistence(service)

    runtime_db = tmp_path / "runtime.db"
    runtime_engine = create_runtime_database_engine(f"sqlite+pysqlite:///{runtime_db}")
    create_runtime_tables(runtime_engine)
    runtime_repository = SqlAlchemyWorkflowRunRepository(
        create_runtime_session_factory(runtime_engine)
    )
    observer = PhoenixRuntimeObserver(
        PhoenixClient(enabled=False),
        environment="test",
        persistence_metadata_supplier=lambda state: annotate_runtime_state(state).metadata,
    )
    runtime = DevelopmentRuntime(
        repository=runtime_repository,
        observer=observer,
        persistence_metadata_resolver=lambda state: annotate_runtime_state(state).metadata,
    )

    state = runtime.start_run(project="lummevia-os", issue_id="OS-802")
    annotate_runtime_state(state)
    runtime_repository.save_run(state)

    TaskQueueRegistry.default().reset()
    SessionRegistry.default().reset()
    SupervisorRegistry.default().reset()
    ProjectMemoryRegistry.default().reset()
    HumanReviewRegistry.default().reset()
    ConversationRegistry.default().reset()
    ResourceRegistry.default().reset()
    TimelineRegistry.default().reset()

    runtime_routes.runtime_repository = runtime_repository
    runtime_routes.runtime_service = DevelopmentRuntime()

    with TestClient(app) as client:
        configure_operational_persistence(service)

        health_response = client.get("/persistence/health")
        assert health_response.status_code == 200
        assert health_response.json()["enabled"] is True

        rehydrate_response = client.post("/persistence/rehydrate")
        assert rehydrate_response.status_code == 200
        assert rehydrate_response.json()["results"]["queues"]["status"] == "ok"

        timeline_response = client.get(f"/timelines/{state.run.run_id}")
        assert timeline_response.status_code == 200
        timeline = timeline_response.json()
        assert timeline["workflow_run_id"] == state.run.run_id
        assert timeline["metadata"]["timeline_event_count"] >= 1


def test_phoenix_runtime_observer_includes_persistence_metadata(tmp_path: Path) -> None:
    service = _build_operational_service(tmp_path)
    configure_operational_persistence(service)

    observer = PhoenixRuntimeObserver(
        PhoenixClient(enabled=False),
        environment="test",
        persistence_metadata_supplier=lambda state: annotate_runtime_state(state).metadata,
    )
    runtime = DevelopmentRuntime(
        observer=observer,
        persistence_metadata_resolver=lambda state: annotate_runtime_state(state).metadata,
    )

    state = runtime.start_run(project="lummevia-os", issue_id="OS-803")
    attributes = observer._build_attributes(state)

    assert attributes["persistence_enabled"] is True
    assert "repository_write_success" in attributes
    assert "repository_read_success" in attributes
    assert "rehydrated_from_storage" in attributes
