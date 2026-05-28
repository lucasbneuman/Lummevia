from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from pydantic import ValidationError
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.handoffs import create_or_get_handoff_and_run
from app.core.youtrack import (
    ensure_youtrack_available,
    load_agent_context_bundle,
    summarize_artifact_for_youtrack,
)
from lummevia_conversations import (
    AuthorType,
    ConversationPhase,
    ConversationRegistry,
    ConversationStatus,
    ConversationThread,
    ConversationThreadNotFoundError,
    apply_founder_message_policy,
    build_approval_state,
    build_initial_founder_pm_state,
    is_explicit_approval,
    update_thread_with_policy_decision,
)
from lummevia_integrations import (
    YouTrackCommentPayload,
    YouTrackConfigurationError,
    YouTrackIntegrationError,
    YouTrackIssueCreatePayload,
    YouTrackProject,
)
from lummevia_reviews import HumanReviewRegistry, ReviewDecision, ReviewType


router = APIRouter(prefix="/telegram", tags=["telegram"])
_pending_telegram_starts: dict[int, dict[str, Any]] = {}


class TelegramChat(BaseModel):
    id: int | None = None
    type: str | None = None


class TelegramUser(BaseModel):
    id: int | None = None
    is_bot: bool = False
    first_name: str | None = None
    username: str | None = None


class TelegramMessage(BaseModel):
    message_id: int | None = None
    date: int | None = None
    chat: TelegramChat | None = None
    text: str | None = None
    from_user: TelegramUser | None = Field(default=None, alias="from")


class TelegramUpdate(BaseModel):
    update_id: int | None = None
    message: TelegramMessage | None = None


class TelegramWebhookResponse(BaseModel):
    ok: bool = True
    action: str = Field(min_length=1)
    project: str | None = None
    issue_id: str | None = None
    thread_id: str | None = None
    youtrack_comment_added: bool = False
    conversation_status: str | None = None
    conversation_phase: str | None = None
    brief_version: int = 0
    approved: bool = False
    pending_questions: list[str] = Field(default_factory=list)
    pending_questions_count: int = 0
    review_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def _validate_secret(secret_token: str | None, query_secret: str | None) -> None:
    configured_secret = settings.telegram.webhook_secret
    if configured_secret is None:
        return
    if secret_token == configured_secret or query_secret == configured_secret:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Telegram webhook secret.",
    )


def _is_allowed_chat(chat_id: int) -> bool:
    allowed_chat_ids = settings.telegram.allowed_chat_ids
    if not allowed_chat_ids:
        return True
    return str(chat_id) in allowed_chat_ids


def _send_telegram_message(chat_id: int, text: str) -> bool:
    bot_token = settings.telegram.bot_token
    if bot_token is None:
        return False

    payload = {
        "chat_id": chat_id,
        "text": text[:4096],
        "disable_web_page_preview": True,
    }
    request = UrlRequest(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return False
    return body.get("ok") is True


def clear_pending_telegram_starts() -> None:
    _pending_telegram_starts.clear()


def _client():
    try:
        return ensure_youtrack_available()
    except YouTrackConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _parse_command(text: str) -> tuple[str, dict[str, str], str]:
    stripped = text.strip()
    if not stripped:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Telegram message text is required.",
        )

    lines = stripped.splitlines()
    first_line = lines[0].strip()
    remainder = "\n".join(lines[1:]).strip()
    parts = first_line.split()
    command = parts[0].lower()
    metadata: dict[str, str] = {}
    for token in parts[1:]:
        if "=" not in token:
            metadata.setdefault("_argument", token.strip())
            continue
        key, value = token.split("=", 1)
        if key and value:
            normalized_key = key.strip().lower()
            if normalized_key == "projetc":
                metadata["project"] = value.strip()
                metadata["_project_key_typo"] = "projetc"
            else:
                metadata[normalized_key] = value.strip()

    if command not in {"/lummevia", "/approve"}:
        command = "/lummevia"
        remainder = stripped

    return command, metadata, remainder


def _resolve_or_create_issue(
    *,
    project: str,
    issue_id: str | None,
    body: str,
) -> str:
    client = _client()
    if issue_id is not None:
        return issue_id
    summary = body.splitlines()[0].strip() if body.strip() else "Telegram founder intent"
    created_issue = client.create_issue(
        YouTrackIssueCreatePayload(
            project=project,
            summary=summary[:120],
            description=body or "Founder intent received from Telegram.",
            tags=["telegram", "founder-intent"],
        )
    )
    return created_issue.issue_id


def _find_existing_thread(
    *,
    project: str,
    issue_id: str,
    chat_id: int,
) -> ConversationThread | None:
    registry = ConversationRegistry.default()
    for thread in registry.list_threads():
        state = thread.founder_pm_state
        if (
            thread.project == project
            and thread.issue_id == issue_id
            and (
                (state is not None and state.telegram_chat_id == chat_id)
                or thread.metadata.get("telegram_chat_id") == chat_id
            )
        ):
            return thread
    return None


def _has_pending_draft(thread: ConversationThread) -> bool:
    state = thread.founder_pm_state
    if state is None:
        return False
    return (
        bool(state.metadata.get("brief_draft"))
        or state.phase == ConversationPhase.PENDING_APPROVAL
    )


def _pending_approval_threads(
    *,
    chat_id: int,
    project: str | None = None,
    issue_id: str | None = None,
) -> list[ConversationThread]:
    threads = []
    for thread in _telegram_threads():
        state = thread.founder_pm_state
        if state is None or state.telegram_chat_id != chat_id:
            continue
        if project is not None and thread.project != project:
            continue
        if issue_id is not None and thread.issue_id != issue_id:
            continue
        if _has_pending_draft(thread):
            threads.append(thread)
    return threads


def _format_pending_approval_choices(threads: list[ConversationThread]) -> str:
    lines = [
        "Hay mas de un Business Brief pendiente. Indicame cual aprobar:",
        "",
    ]
    for thread in threads:
        lines.append(f"- {thread.issue_id} ({thread.project})")
    lines.extend(["", "Ejemplo:", f"/approve issue={threads[0].issue_id}"])
    return "\n".join(lines)


def _telegram_threads() -> list[ConversationThread]:
    return [
        thread
        for thread in ConversationRegistry.default().list_threads()
        if thread.founder_pm_state is not None
        and thread.founder_pm_state.telegram_chat_id is not None
    ]


def _list_youtrack_projects() -> list[YouTrackProject]:
    return sorted(
        _client().list_projects(),
        key=lambda project: project.short_name.casefold(),
    )


def _format_project_selection_message(projects: list[YouTrackProject]) -> str:
    if not projects:
        return "No encontre proyectos activos en YouTrack para seleccionar."
    lines = ["Sobre que proyecto queres trabajar?", ""]
    for project in projects:
        lines.append(f"- {project.short_name} - {project.name}")
    lines.extend(["", "Responde con el codigo del proyecto, por ejemplo: LUM"])
    return "\n".join(lines)


def _project_by_short_name(
    projects: list[YouTrackProject],
    short_name: str,
) -> YouTrackProject | None:
    normalized = short_name.strip().casefold()
    for project in projects:
        if project.short_name.casefold() == normalized:
            return project
    return None


def _project_selection_value(metadata: dict[str, str], body: str) -> str | None:
    for candidate in (metadata.get("project"), metadata.get("_argument")):
        if candidate is not None and candidate.strip():
            return candidate.strip()
    first_line = body.strip().splitlines()[0].strip() if body.strip() else ""
    if first_line and " " not in first_line and "=" not in first_line:
        return first_line
    return None


def _request_project_selection(
    *,
    message: TelegramMessage,
    update: TelegramUpdate,
    initial_intent: str,
) -> TelegramWebhookResponse:
    try:
        projects = _list_youtrack_projects()
        response_text = _format_project_selection_message(projects)
        ignored_reason = None
    except (YouTrackConfigurationError, YouTrackIntegrationError) as exc:
        projects = []
        response_text = (
            "No pude consultar los proyectos de YouTrack. "
            f"Detalle operativo: {exc}"
        )
        ignored_reason = "youtrack_projects_unavailable"

    chat_id = message.chat.id if message.chat is not None else None
    if chat_id is not None and projects:
        _pending_telegram_starts[chat_id] = {
            "status": "AWAITING_PROJECT",
            "initial_intent": initial_intent,
            "project_short_names": [project.short_name for project in projects],
            "telegram_update_id": update.update_id,
            "telegram_message_id": message.message_id,
        }
    telegram_response_sent = _send_telegram_message(chat_id or 0, response_text)
    return TelegramWebhookResponse(
        action="project_selection_requested",
        metadata={
            **_build_thread_metadata(message, update),
            "ignored_reason": ignored_reason,
            "project_count": len(projects),
            "telegram_response_sent": telegram_response_sent,
        },
    )


def _request_intent(
    *,
    project: str,
    message: TelegramMessage,
    update: TelegramUpdate,
    metadata: dict[str, str],
) -> TelegramWebhookResponse:
    chat_id = message.chat.id if message.chat is not None else None
    if chat_id is not None:
        _pending_telegram_starts[chat_id] = {
            "status": "AWAITING_INTENT",
            "project": project,
            "telegram_update_id": update.update_id,
            "telegram_message_id": message.message_id,
        }
    telegram_response_sent = _send_telegram_message(
        chat_id or 0,
        (
            f"Listo, trabajamos sobre {project}. "
            "Contame que queres construir o resolver."
        ),
    )
    return TelegramWebhookResponse(
        action="intent_requested",
        project=project,
        metadata={
            **_build_thread_metadata(message, update),
            "project_key_typo": metadata.get("_project_key_typo"),
            "telegram_response_sent": telegram_response_sent,
        },
    )


def _resolve_project_from_pending_selection(
    *,
    message: TelegramMessage,
    update: TelegramUpdate,
    metadata: dict[str, str],
    body: str,
) -> tuple[str | None, str, TelegramWebhookResponse | None]:
    chat_id = message.chat.id if message.chat is not None else None
    if chat_id is None:
        return None, body, None

    pending = _pending_telegram_starts.get(chat_id)
    if pending is None:
        return None, body, None

    if pending.get("status") == "AWAITING_INTENT":
        project = str(pending.get("project") or "")
        if not project:
            _pending_telegram_starts.pop(chat_id, None)
            return None, body, None
        intent = body.strip() or metadata.get("_argument", "").strip()
        if not intent:
            return project, body, _request_intent(
                project=project,
                message=message,
                update=update,
                metadata=metadata,
            )
        _pending_telegram_starts.pop(chat_id, None)
        return project, intent, None

    candidate = _project_selection_value(metadata, body)
    if candidate is None:
        return None, body, _request_project_selection(
            message=message,
            update=update,
            initial_intent=str(pending.get("initial_intent") or ""),
        )

    try:
        projects = _list_youtrack_projects()
    except (YouTrackConfigurationError, YouTrackIntegrationError) as exc:
        telegram_response_sent = _send_telegram_message(
            chat_id,
            (
                "No pude validar el proyecto contra YouTrack. "
                f"Detalle operativo: {exc}"
            ),
        )
        return None, body, TelegramWebhookResponse(
            action="project_selection_requested",
            metadata={
                **_build_thread_metadata(message, update),
                "ignored_reason": "youtrack_projects_unavailable",
                "telegram_response_sent": telegram_response_sent,
            },
        )

    project = _project_by_short_name(projects, candidate)
    if project is None:
        telegram_response_sent = _send_telegram_message(
            chat_id,
            "No reconozco ese proyecto.\n\n" + _format_project_selection_message(projects),
        )
        return None, body, TelegramWebhookResponse(
            action="project_selection_requested",
            metadata={
                **_build_thread_metadata(message, update),
                "ignored_reason": "unknown_project",
                "project_candidate": candidate,
                "project_count": len(projects),
                "telegram_response_sent": telegram_response_sent,
            },
        )

    initial_intent = str(pending.get("initial_intent") or "").strip()
    if not initial_intent:
        return project.short_name, body, _request_intent(
            project=project.short_name,
            message=message,
            update=update,
            metadata=metadata,
        )

    _pending_telegram_starts.pop(chat_id, None)
    return project.short_name, initial_intent, None


def _build_thread_metadata(message: TelegramMessage, update: TelegramUpdate) -> dict[str, Any]:
    return {
        "telegram_chat_id": message.chat.id if message.chat is not None else None,
        "telegram_user_id": message.from_user.id if message.from_user is not None else None,
        "telegram_username": message.from_user.username if message.from_user is not None else None,
        "telegram_message_id": message.message_id,
        "telegram_update_id": update.update_id,
    }


def _build_youtrack_context(project: str, issue_id: str) -> dict[str, Any]:
    bundle = load_agent_context_bundle(project=project, role="PM", issue_id=issue_id)
    return bundle.model_dump(mode="json") if bundle is not None else {}


def _sync_founder_message(issue_id: str, founder_message: str, message_id: int | None) -> None:
    _client().add_comment(
        issue_id,
        YouTrackCommentPayload(
            body=(
                "Founder response received from Telegram.\n"
                f"message_id: {message_id}\n\n"
                f"{founder_message}"
            ).strip()
        ),
    )


def _sync_pm_questions(issue_id: str, pm_message: str) -> None:
    _client().add_comment(
        issue_id,
        YouTrackCommentPayload(
            body=f"PM needs clarification before drafting.\n\n{pm_message}"
        ),
    )


def _sync_brief_draft(issue_id: str, brief_draft: dict[str, Any]) -> None:
    payload = dict(brief_draft)
    payload.pop("created_at", None)
    _client().add_comment(
        issue_id,
        YouTrackCommentPayload(
            body=summarize_artifact_for_youtrack(
                artifact_type="BusinessBriefDraft",
                payload=payload,
            )
        ),
    )


def _sync_approval(issue_id: str, thread_id: str, message_id: int | None, review_id: str) -> None:
    _client().add_comment(
        issue_id,
        YouTrackCommentPayload(
            body=(
                "Founder approved the Business Brief from Telegram.\n"
                f"thread_id: {thread_id}\n"
                f"review_id: {review_id}\n"
                f"message_id: {message_id}"
            )
        ),
    )


def _create_review_for_approval(thread: ConversationThread) -> str:
    state = thread.founder_pm_state
    if state is None:
        raise ValueError("Founder PM state is required before creating a review.")
    review = HumanReviewRegistry.default().create_review(
        review_type=ReviewType.BUSINESS_BRIEF,
        target_id=thread.issue_id,
        target_type="BusinessBrief",
        requested_by="PM",
        assigned_to="FOUNDER",
        notes="Founder explicit approval from Telegram.",
        metadata={
            "project": thread.project,
            "issue_id": thread.issue_id,
            "thread_id": thread.thread_id,
            "brief_version": state.brief_version,
            "conversation_phase": state.phase.value,
        },
    )
    review = HumanReviewRegistry.default().complete_review(
        review.review_id,
        decision=ReviewDecision.APPROVED,
        notes="Founder approved explicitly from Telegram.",
        assigned_to="FOUNDER",
    )
    return review.review_id


def _response_for_thread(
    *,
    action: str,
    project: str,
    issue_id: str,
    thread: ConversationThread,
    youtrack_comment_added: bool,
    review_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TelegramWebhookResponse:
    state = thread.founder_pm_state
    return TelegramWebhookResponse(
        action=action,
        project=project,
        issue_id=issue_id,
        thread_id=thread.thread_id,
        youtrack_comment_added=youtrack_comment_added,
        conversation_status=thread.status.value,
        conversation_phase=state.phase.value if state is not None else None,
        brief_version=state.brief_version if state is not None else 0,
        approved=state.approved if state is not None else False,
        pending_questions=state.pending_questions if state is not None else [],
        pending_questions_count=len(state.pending_questions) if state is not None else 0,
        review_id=review_id,
        metadata=metadata or {},
    )


@router.get("/conversations", response_model=list[ConversationThread])
def list_telegram_conversations() -> list[ConversationThread]:
    return _telegram_threads()


@router.get("/conversations/{thread_id}", response_model=ConversationThread)
def get_telegram_conversation(thread_id: str) -> ConversationThread:
    try:
        thread = ConversationRegistry.default().get_thread(thread_id)
    except ConversationThreadNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.args[0],
        ) from exc
    if thread.founder_pm_state is None or thread.founder_pm_state.telegram_chat_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Telegram conversation '{thread_id}' not found.",
        )
    return thread


@router.post("/webhook", response_model=TelegramWebhookResponse)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    secret: str | None = Query(default=None),
) -> TelegramWebhookResponse:
    _validate_secret(x_telegram_bot_api_secret_token, secret)

    raw_body = await request.body()
    if not raw_body:
        return TelegramWebhookResponse(
            action="ignored",
            metadata={"ignored_reason": "missing_request_body"},
        )

    try:
        update = TelegramUpdate.model_validate_json(raw_body)
    except (ValueError, ValidationError) as exc:
        return TelegramWebhookResponse(
            action="ignored",
            metadata={
                "ignored_reason": "invalid_update_payload",
                "error": str(exc),
            },
        )

    message = update.message
    if message is None or not message.text:
        return TelegramWebhookResponse(
            action="ignored",
            metadata={
                "ignored_reason": "missing_message_text",
                "telegram_update_id": update.update_id,
            },
        )

    if (
        message.chat is None
        or message.chat.id is None
        or message.from_user is None
        or message.from_user.id is None
    ):
        return TelegramWebhookResponse(
            action="ignored",
            metadata={
                "ignored_reason": "missing_message_context",
                "telegram_update_id": update.update_id,
                "telegram_message_id": message.message_id,
            },
        )

    if not _is_allowed_chat(message.chat.id):
        return TelegramWebhookResponse(
            action="ignored",
            metadata={
                "ignored_reason": "chat_not_allowed",
                "telegram_update_id": update.update_id,
                "telegram_message_id": message.message_id,
                "telegram_chat_id": message.chat.id,
            },
        )

    command, metadata, body = _parse_command(message.text)
    project = metadata.get("project")
    registry = ConversationRegistry.default()
    existing_thread: ConversationThread | None = None

    if command == "/approve":
        candidate_threads = _pending_approval_threads(
            chat_id=message.chat.id,
            project=project,
            issue_id=metadata.get("issue"),
        )
        if project is None and metadata.get("issue") is None:
            if not candidate_threads:
                telegram_response_sent = _send_telegram_message(
                    message.chat.id,
                    "No hay Business Brief pendiente de aprobacion para este chat.",
                )
                return TelegramWebhookResponse(
                    action="approval_context_required",
                    metadata={
                        **_build_thread_metadata(message, update),
                        "ignored_reason": "no_pending_approval",
                        "telegram_response_sent": telegram_response_sent,
                    },
                )
            if len(candidate_threads) > 1:
                telegram_response_sent = _send_telegram_message(
                    message.chat.id,
                    _format_pending_approval_choices(candidate_threads),
                )
                return TelegramWebhookResponse(
                    action="approval_context_required",
                    metadata={
                        **_build_thread_metadata(message, update),
                        "ignored_reason": "multiple_pending_approvals",
                        "pending_approval_count": len(candidate_threads),
                        "telegram_response_sent": telegram_response_sent,
                    },
                )
        if len(candidate_threads) == 1:
            existing_thread = candidate_threads[0]
            project = existing_thread.project
            metadata["issue"] = existing_thread.issue_id

    if project is None:
        pending_project, pending_body, pending_response = _resolve_project_from_pending_selection(
            message=message,
            update=update,
            metadata=metadata,
            body=body,
        )
        if pending_response is not None:
            return pending_response
        project = pending_project
        body = pending_body

    if project is None:
        return _request_project_selection(
            message=message,
            update=update,
            initial_intent=body,
        )

    if not body and command == "/lummevia" and metadata.get("issue") is None:
        return _request_intent(
            project=project,
            message=message,
            update=update,
            metadata=metadata,
        )

    issue_id = metadata.get("issue")
    if existing_thread is None:
        issue_id = _resolve_or_create_issue(
            project=project,
            issue_id=issue_id,
            body=body,
        )
        existing_thread = _find_existing_thread(
            project=project,
            issue_id=issue_id,
            chat_id=message.chat.id,
        )
    else:
        issue_id = existing_thread.issue_id

    if existing_thread is None:
        founder_pm_state = build_initial_founder_pm_state(
            thread_id="seed-thread-id",
            project=project,
            issue_id=issue_id,
            telegram_chat_id=message.chat.id,
            metadata={"source": "telegram"},
        )
        thread = registry.create_thread(
            topic=f"Telegram founder conversation for {issue_id}",
            project=project,
            issue_id=issue_id,
            founder_pm_state=founder_pm_state,
            metadata={
                "telegram_chat_id": message.chat.id,
                "telegram_user_id": message.from_user.id,
                "telegram_username": message.from_user.username,
            },
        )
        thread = thread.model_copy(
            update={
                "founder_pm_state": founder_pm_state.model_copy(
                    update={"thread_id": thread.thread_id}
                )
            }
        )
        registry.save_thread(thread)
    else:
        thread = existing_thread

    founder_message = (
        body
        if body
        else "approve"
        if command == "/approve"
        else "Founder intent received from Telegram."
    )
    thread = registry.add_message(
        thread.thread_id,
        role="user",
        author_type=AuthorType.FOUNDER,
        content=founder_message,
        metadata={
            **_build_thread_metadata(message, update),
            "source": "telegram",
            "command": command,
            "conversation_event": "FOUNDER_RESPONSE_RECEIVED",
            "project_key_typo": metadata.get("_project_key_typo"),
        },
    )

    state = thread.founder_pm_state or build_initial_founder_pm_state(
        thread_id=thread.thread_id,
        project=project,
        issue_id=issue_id,
        telegram_chat_id=message.chat.id,
    )
    if _has_pending_draft(thread) and (
        command == "/approve" or is_explicit_approval(founder_message)
    ):
        review_id = _create_review_for_approval(thread)
        approved_state = build_approval_state(
            state,
            approval_message=founder_message,
            review_id=review_id,
            now=datetime.now(UTC),
        )
        thread = thread.model_copy(
            update={
                "status": ConversationStatus.APPROVED,
                "founder_pm_state": approved_state,
                "updated_at": datetime.now(UTC),
            }
        )
        registry.save_thread(thread)
        _sync_approval(issue_id, thread.thread_id, message.message_id, review_id)
        handoff, runtime_state = create_or_get_handoff_and_run(thread_id=thread.thread_id)
        telegram_response_sent = _send_telegram_message(
            message.chat.id,
            (
                "Aprobacion recibida. El Business Brief quedo aprobado y "
                "se creo el handoff tecnico."
            ),
        )
        return _response_for_thread(
            action="approved",
            project=project,
            issue_id=issue_id,
            thread=thread,
            youtrack_comment_added=True,
            review_id=review_id,
            metadata={
                **_build_thread_metadata(message, update),
                "handoff_id": handoff.handoff_id,
                "workflow_run_id": runtime_state.run.run_id,
                "telegram_response_sent": telegram_response_sent,
            },
        )

    _sync_founder_message(issue_id, founder_message, message.message_id)
    youtrack_context = _build_youtrack_context(project, issue_id)
    decision = apply_founder_message_policy(
        thread,
        founder_message=founder_message,
        youtrack_context=youtrack_context,
    )
    thread = update_thread_with_policy_decision(thread, decision)
    registry.save_thread(thread)

    if decision.last_pm_message is not None:
        pm_event_type = (
            "PM_QUESTION_SENT"
            if decision.phase == ConversationPhase.PM_QUESTIONS
            else "BRIEF_DRAFT_CREATED"
        )
        thread = registry.add_message(
            thread.thread_id,
            role="assistant",
            author_type=AuthorType.PM,
            content=decision.last_pm_message,
            metadata={
                "source": "telegram",
                "conversation_event": pm_event_type,
                "brief_version": decision.brief_version,
                "pending_questions_count": len(decision.pending_questions),
            },
        )

    if decision.phase == ConversationPhase.PM_QUESTIONS:
        _sync_pm_questions(issue_id, decision.last_pm_message or "")
        telegram_response_sent = _send_telegram_message(
            message.chat.id,
            decision.last_pm_message or "Necesito mas contexto para avanzar.",
        )
        return _response_for_thread(
            action="pm_questions",
            project=project,
            issue_id=issue_id,
            thread=thread,
            youtrack_comment_added=True,
            metadata={
                **_build_thread_metadata(message, update),
                "youtrack_context_loaded": bool(youtrack_context),
                "telegram_response_sent": telegram_response_sent,
            },
        )

    if decision.brief_draft is not None:
        _sync_brief_draft(issue_id, decision.brief_draft)
        telegram_response_sent = _send_telegram_message(
            message.chat.id,
            (
                (decision.last_pm_message or "Business Brief draft creado.")
                + "\n\nPara aprobarlo, responde:\n"
                "/approve"
            ),
        )
        return _response_for_thread(
            action="pending_approval",
            project=project,
            issue_id=issue_id,
            thread=thread,
            youtrack_comment_added=True,
            metadata={
                **_build_thread_metadata(message, update),
                "youtrack_context_loaded": bool(youtrack_context),
                "brief_draft_created_at": decision.metadata.get("draft_created_at"),
                "telegram_response_sent": telegram_response_sent,
            },
        )

    telegram_response_sent = _send_telegram_message(
        message.chat.id,
        f"Recibido. Actualice la conversacion para {issue_id}.",
    )
    return _response_for_thread(
        action="captured",
        project=project,
        issue_id=issue_id,
        thread=thread,
        youtrack_comment_added=True,
        metadata={
            **_build_thread_metadata(message, update),
            "youtrack_context_loaded": bool(youtrack_context),
            "telegram_response_sent": telegram_response_sent,
        },
    )
