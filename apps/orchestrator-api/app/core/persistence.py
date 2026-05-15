from __future__ import annotations

from typing import Any

from lummevia_capabilities import CapabilityRegistry
from lummevia_core import ApprovedProjectHandoffRegistry
from lummevia_conversations import ConversationRegistry
from lummevia_memory import ProjectMemoryRegistry
from lummevia_planning import AdaptivePlanRegistry
from lummevia_persistence import OperationalPersistenceService
from lummevia_queue import TaskQueueRegistry
from lummevia_resources import ResourceRegistry
from lummevia_reviews import HumanReviewRegistry
from lummevia_sessions import SessionRegistry
from lummevia_supervisor import SupervisorRegistry


operational_persistence: OperationalPersistenceService | None = None
rehydration_completed = False


def configure_operational_persistence(
    service: OperationalPersistenceService | None,
) -> None:
    global operational_persistence, rehydration_completed

    operational_persistence = service
    rehydration_completed = False

    TaskQueueRegistry.default().configure_persistence(
        None if service is None else service.queues
    )
    SessionRegistry.default().configure_persistence(
        None if service is None else service.sessions
    )
    SupervisorRegistry.default().configure_persistence(
        None if service is None else service.supervisor
    )
    ProjectMemoryRegistry.default().configure_persistence(
        None if service is None else service.memory
    )
    AdaptivePlanRegistry.default().configure_persistence(
        None if service is None else service.planning
    )
    HumanReviewRegistry.default().configure_persistence(
        None if service is None else service.reviews
    )
    ConversationRegistry.default().configure_persistence(
        None if service is None else service.conversations
    )
    ApprovedProjectHandoffRegistry.default().configure_persistence(
        None if service is None else service.handoffs
    )
    ResourceRegistry.default().configure_persistence(
        None if service is None else service.resources
    )
    CapabilityRegistry.default().configure_persistence(
        None if service is None else service.capabilities
    )


def rehydrate_registries() -> dict[str, dict[str, Any]]:
    global rehydration_completed

    if operational_persistence is None:
        rehydration_completed = False
        return {}

    results: dict[str, dict[str, Any]] = {}

    try:
        queues = operational_persistence.queues.list_queues()
        TaskQueueRegistry.default().rehydrate(queues)
        results["queues"] = {"status": "ok", "count": len(queues)}
    except Exception as exc:
        results["queues"] = {"status": "error", "detail": str(exc)}

    try:
        sessions = operational_persistence.sessions.list_sessions()
        SessionRegistry.default().rehydrate(sessions)
        results["sessions"] = {"status": "ok", "count": len(sessions)}
    except Exception as exc:
        results["sessions"] = {"status": "error", "detail": str(exc)}

    try:
        SupervisorRegistry.default().rehydrate(
            events=operational_persistence.supervisor.list_events(),
            watchdogs=operational_persistence.supervisor.list_watchdogs(),
            recovery_actions=operational_persistence.supervisor.list_recovery_actions(),
            dead_letters=operational_persistence.supervisor.list_dead_letters(),
        )
        results["supervisor"] = {
            "status": "ok",
            "watchdogs": len(SupervisorRegistry.default().list_watchdogs()),
            "dead_letters": len(SupervisorRegistry.default().list_dead_letters()),
        }
    except Exception as exc:
        results["supervisor"] = {"status": "error", "detail": str(exc)}

    try:
        memories = operational_persistence.memory.list_records()
        ProjectMemoryRegistry.default().rehydrate(memories)
        results["memory"] = {"status": "ok", "count": len(memories)}
    except Exception as exc:
        results["memory"] = {"status": "error", "detail": str(exc)}

    try:
        plans = operational_persistence.planning.list_plans()
        AdaptivePlanRegistry.default().rehydrate(plans)
        results["planning"] = {"status": "ok", "count": len(plans)}
    except Exception as exc:
        results["planning"] = {"status": "error", "detail": str(exc)}

    try:
        reviews = operational_persistence.reviews.list_reviews()
        HumanReviewRegistry.default().rehydrate(reviews)
        results["reviews"] = {"status": "ok", "count": len(reviews)}
    except Exception as exc:
        results["reviews"] = {"status": "error", "detail": str(exc)}

    try:
        threads = operational_persistence.conversations.list_threads()
        ConversationRegistry.default().rehydrate(threads)
        results["conversations"] = {"status": "ok", "count": len(threads)}
    except Exception as exc:
        results["conversations"] = {"status": "error", "detail": str(exc)}

    try:
        handoffs = operational_persistence.handoffs.list_handoffs()
        ApprovedProjectHandoffRegistry.default().rehydrate(handoffs)
        results["handoffs"] = {"status": "ok", "count": len(handoffs)}
    except Exception as exc:
        results["handoffs"] = {"status": "error", "detail": str(exc)}

    try:
        ResourceRegistry.default().rehydrate(
            locks=operational_persistence.resources.list_locks(),
            workspaces=operational_persistence.resources.list_workspaces(),
        )
        results["resources"] = {
            "status": "ok",
            "locks": len(ResourceRegistry.default().list_locks()),
            "workspaces": len(ResourceRegistry.default().list_workspaces()),
        }
    except Exception as exc:
        results["resources"] = {"status": "error", "detail": str(exc)}

    try:
        capability_states = operational_persistence.capabilities.list_states()
        if capability_states:
            CapabilityRegistry.default().rehydrate(capability_states[-1])
        results["capabilities"] = {
            "status": "ok",
            "count": len(capability_states),
        }
    except Exception as exc:
        results["capabilities"] = {"status": "error", "detail": str(exc)}

    rehydration_completed = any(result["status"] == "ok" for result in results.values())
    return results


def resolve_runtime_persistence_metadata(state) -> dict[str, Any]:
    if operational_persistence is None:
        return {
            "persistence_enabled": False,
            "repository_write_success": False,
            "repository_read_success": False,
            "rehydrated_from_storage": False,
        }

    health = operational_persistence.health()
    versions = _resolve_snapshot_versions(state)
    metadata = {
        "persistence_enabled": True,
        "repository_write_success": all(
            item.error_count == 0 and item.last_write_at is not None for item in health
        ),
        "repository_read_success": all(
            item.error_count == 0 and item.last_read_at is not None for item in health
        ),
        "rehydrated_from_storage": bool(rehydration_completed),
    }
    if versions:
        metadata["snapshot_version"] = max(versions)
    return metadata


def annotate_runtime_state(state):
    state.metadata.update(resolve_runtime_persistence_metadata(state))
    return state


def _resolve_snapshot_versions(state) -> list[int]:
    if operational_persistence is None:
        return []

    candidates = [
        ("queue", state.metadata.get("queue_id")),
        ("session", state.metadata.get("current_session_id")),
        ("conversation", state.metadata.get("thread_id")),
        ("handoff", state.metadata.get("handoff_id")),
        ("workspace", state.metadata.get("workspace_id")),
        ("dead_letter", state.metadata.get("dead_letter_id")),
        ("adaptive_plan", state.metadata.get("adaptive_plan_id")),
    ]
    versions: list[int] = []
    for entity_type, entity_id in candidates:
        if not entity_id:
            continue
        version = operational_persistence.snapshot_version_for(entity_type, str(entity_id))
        if version is not None:
            versions.append(version)
    return versions
