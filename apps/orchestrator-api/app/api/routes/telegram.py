from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.youtrack import ensure_youtrack_available
from lummevia_conversations import (
    AuthorType,
    ConversationRegistry,
    ConversationStatus,
    ConversationThread,
)
from lummevia_integrations import (
    YouTrackCommentPayload,
    YouTrackConfigurationError,
    YouTrackIssueCreatePayload,
)


router = APIRouter(prefix="/telegram", tags=["telegram"])


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
    metadata: dict[str, Any] = Field(default_factory=dict)


def _validate_secret(secret_token: str | None) -> None:
    configured_secret = settings.telegram.webhook_secret
    if configured_secret is None:
        return
    if secret_token == configured_secret:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Telegram webhook secret.",
    )


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
            continue
        key, value = token.split("=", 1)
        if key and value:
            metadata[key.strip().lower()] = value.strip()

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


def _find_existing_thread(*, project: str, issue_id: str, chat_id: int) -> ConversationThread | None:
    registry = ConversationRegistry.default()
    for thread in registry.list_threads():
        if (
            thread.project == project
            and thread.issue_id == issue_id
            and thread.metadata.get("telegram_chat_id") == chat_id
        ):
            return thread
    return None


@router.post("/webhook", response_model=TelegramWebhookResponse)
def telegram_webhook(
    update: TelegramUpdate,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> TelegramWebhookResponse:
    _validate_secret(x_telegram_bot_api_secret_token)

    message = update.message
    if message is None or not message.text:
        return TelegramWebhookResponse(
            action="ignored",
            metadata={
                "ignored_reason": "missing_message_text",
                "telegram_update_id": update.update_id,
            },
        )

    if message.chat is None or message.chat.id is None or message.from_user is None or message.from_user.id is None:
        return TelegramWebhookResponse(
            action="ignored",
            metadata={
                "ignored_reason": "missing_message_context",
                "telegram_update_id": update.update_id,
                "telegram_message_id": message.message_id,
            },
        )

    command, metadata, body = _parse_command(message.text)
    project = metadata.get("project")
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Telegram command must include project=<shortName>.",
        )

    issue_id = _resolve_or_create_issue(
        project=project,
        issue_id=metadata.get("issue"),
        body=body,
    )
    registry = ConversationRegistry.default()
    existing_thread = _find_existing_thread(
        project=project,
        issue_id=issue_id,
        chat_id=message.chat.id,
    )
    thread = existing_thread or registry.create_thread(
        topic=f"Telegram founder conversation for {issue_id}",
        project=project,
        issue_id=issue_id,
        metadata={
            "telegram_chat_id": message.chat.id,
            "telegram_user_id": message.from_user.id,
            "telegram_username": message.from_user.username,
        },
    )

    founder_message = (
        body
        if body
        else "Founder requested approval from Telegram."
        if command == "/approve"
        else "Founder intent received from Telegram."
    )
    registry.add_message(
        thread.thread_id,
        role="user",
        author_type=AuthorType.FOUNDER,
        content=founder_message,
        metadata={
            "source": "telegram",
            "telegram_message_id": message.message_id,
            "telegram_update_id": update.update_id,
            "command": command,
        },
    )

    if command == "/approve":
        thread = registry.update_thread_status(
            thread.thread_id,
            ConversationStatus.APPROVED,
            metadata={"approved_via": "telegram"},
        )
        comment_body = (
            "Founder approved the Business Brief gate from Telegram.\n"
            f"message_id: {message.message_id}"
        )
        action = "approved"
    else:
        comment_body = (
            "Founder intent received from Telegram.\n"
            f"message_id: {message.message_id}\n\n"
            f"{founder_message}"
        )
        action = "captured"

    _client().add_comment(issue_id, YouTrackCommentPayload(body=comment_body))
    current_thread = registry.get_thread(thread.thread_id)
    return TelegramWebhookResponse(
        action=action,
        project=project,
        issue_id=issue_id,
        thread_id=current_thread.thread_id,
        youtrack_comment_added=True,
        conversation_status=current_thread.status.value,
        metadata={
            "telegram_chat_id": message.chat.id,
            "telegram_user_id": message.from_user.id,
            "telegram_message_id": message.message_id,
            "telegram_update_id": update.update_id,
        },
    )
