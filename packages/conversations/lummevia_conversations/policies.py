from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lummevia_conversations.schemas import (
    AuthorType,
    ConversationPhase,
    ConversationStatus,
    FounderPMConversationState,
    ConversationThread,
)

MAX_QUESTIONS_PER_ITERATION = 3
MAX_ITERATIONS = 5


class ContractField(StrEnum):
    OBJECTIVE = "objective"
    CONSTRAINTS = "constraints"
    USER = "user"
    SCOPE = "scope"
    EXPECTED_SUCCESS = "expected_success"


class FounderPMPolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: ConversationPhase
    thread_status: ConversationStatus
    iteration_count: int = Field(ge=0)
    pending_questions: list[str] = Field(default_factory=list)
    pending_question_fields: list[str] = Field(default_factory=list)
    last_pm_message: str | None = None
    brief_version: int = Field(default=0, ge=0)
    approved: bool = False
    contract_context: dict[str, Any] = Field(default_factory=dict)
    brief_draft: dict[str, Any] | None = None
    needs_youtrack_draft_sync: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


def build_initial_founder_pm_state(
    *,
    thread_id: str,
    project: str,
    issue_id: str | None,
    telegram_chat_id: int | None,
    metadata: dict[str, Any] | None = None,
) -> FounderPMConversationState:
    return FounderPMConversationState(
        thread_id=thread_id,
        telegram_chat_id=telegram_chat_id,
        project=project,
        issue_id=issue_id,
        phase=ConversationPhase.STARTED,
        metadata=metadata or {},
    )


def is_explicit_approval(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    return normalized in {
        "approve",
        "approved",
        "aprobar",
        "ok aprobar",
        "ok, aprobar",
        "confirmo",
        "confirmado",
        "aprobado",
        "ok aprobado",
        "ok, aprobado",
    }


def apply_founder_message_policy(
    thread: ConversationThread,
    *,
    founder_message: str,
    youtrack_context: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> FounderPMPolicyDecision:
    timestamp = now or datetime.now(UTC)
    state = thread.founder_pm_state or build_initial_founder_pm_state(
        thread_id=thread.thread_id,
        project=thread.project,
        issue_id=thread.issue_id,
        telegram_chat_id=_as_int(thread.metadata.get("telegram_chat_id")),
        metadata={"created_from": "policy"},
    )
    contract_context = _build_contract_context(
        thread,
        founder_message=founder_message,
        state=state,
        youtrack_context=youtrack_context or {},
    )
    missing_fields = _find_missing_fields(contract_context)

    if not missing_fields or state.iteration_count >= MAX_ITERATIONS:
        brief_version = max(state.brief_version, 0) + 1
        brief_draft = _build_brief_draft(
            thread,
            contract_context=contract_context,
            brief_version=brief_version,
            timestamp=timestamp,
            force_assumptions=bool(missing_fields),
        )
        pm_message = _build_draft_message(
            brief_draft=brief_draft,
            missing_fields=missing_fields,
        )
        return FounderPMPolicyDecision(
            phase=ConversationPhase.PENDING_APPROVAL,
            thread_status=ConversationStatus.ACTIVE,
            iteration_count=state.iteration_count,
            pending_questions=[],
            pending_question_fields=[],
            last_pm_message=pm_message,
            brief_version=brief_version,
            approved=False,
            contract_context=contract_context,
            brief_draft=brief_draft,
            needs_youtrack_draft_sync=True,
            metadata={
                "draft_created_at": timestamp.isoformat(),
                "max_iterations_reached": state.iteration_count >= MAX_ITERATIONS,
            },
        )

    question_fields = missing_fields[:MAX_QUESTIONS_PER_ITERATION]
    questions = [_question_for_field(ContractField(field_name)) for field_name in question_fields]
    pm_message = _format_questions(questions)
    return FounderPMPolicyDecision(
        phase=ConversationPhase.PM_QUESTIONS,
        thread_status=ConversationStatus.ACTIVE,
        iteration_count=state.iteration_count + 1,
        pending_questions=questions,
        pending_question_fields=question_fields,
        last_pm_message=pm_message,
        brief_version=state.brief_version,
        approved=False,
        contract_context=contract_context,
        metadata={
            "last_question_batch_at": timestamp.isoformat(),
        },
    )


def build_approval_state(
    state: FounderPMConversationState,
    *,
    approval_message: str,
    review_id: str,
    now: datetime | None = None,
) -> FounderPMConversationState:
    timestamp = now or datetime.now(UTC)
    metadata = dict(state.metadata)
    metadata.update(
        {
            "review_id": review_id,
            "approved_at": timestamp.isoformat(),
            "approval_message": approval_message,
        }
    )
    return state.model_copy(
        update={
            "phase": ConversationPhase.APPROVED,
            "pending_questions": [],
            "approved": True,
            "metadata": metadata,
        }
    )


def update_thread_with_policy_decision(
    thread: ConversationThread,
    decision: FounderPMPolicyDecision,
) -> ConversationThread:
    previous_state = thread.founder_pm_state or build_initial_founder_pm_state(
        thread_id=thread.thread_id,
        project=thread.project,
        issue_id=thread.issue_id,
        telegram_chat_id=_as_int(thread.metadata.get("telegram_chat_id")),
    )
    merged_metadata = dict(previous_state.metadata)
    merged_metadata.update(decision.metadata)
    merged_metadata["contract_context"] = decision.contract_context
    if decision.brief_draft is not None:
        merged_metadata["brief_draft"] = decision.brief_draft
    if decision.pending_question_fields:
        merged_metadata["pending_question_fields"] = decision.pending_question_fields
    else:
        merged_metadata.pop("pending_question_fields", None)

    updated_state = previous_state.model_copy(
        update={
            "phase": decision.phase,
            "iteration_count": decision.iteration_count,
            "brief_version": decision.brief_version,
            "last_pm_message": decision.last_pm_message,
            "pending_questions": decision.pending_questions,
            "approved": decision.approved,
            "metadata": merged_metadata,
        }
    )
    return thread.model_copy(
        update={
            "status": decision.thread_status,
            "founder_pm_state": updated_state,
            "updated_at": datetime.now(UTC),
        }
    )


def _build_contract_context(
    thread: ConversationThread,
    *,
    founder_message: str,
    state: FounderPMConversationState,
    youtrack_context: dict[str, Any],
) -> dict[str, Any]:
    previous_context = state.metadata.get("contract_context", {})
    if not isinstance(previous_context, dict):
        previous_context = {}
    context = dict(previous_context)

    lines = _extract_answer_lines(founder_message)
    pending_fields = state.metadata.get("pending_question_fields", [])
    if isinstance(pending_fields, list) and pending_fields:
        for field_name, answer in zip(pending_fields, lines, strict=False):
            if answer:
                context[field_name] = answer

    if not context.get(ContractField.OBJECTIVE.value) and founder_message.strip():
        context[ContractField.OBJECTIVE.value] = founder_message.strip()

    lowered = _normalize_text(founder_message)
    line_map = {
        ContractField.USER.value: ("usuario", "usuarios", "user", "perfil"),
        ContractField.SCOPE.value: ("alcance", "scope", "mvp", "incluye", "incluir", "solo"),
        ContractField.CONSTRAINTS.value: (
            "restric",
            "sin ",
            "evitar",
            "maximo",
            "máximo",
            "presupuesto",
            "deadline",
            "compliance",
        ),
        ContractField.EXPECTED_SUCCESS.value: (
            "exito",
            "éxito",
            "kpi",
            "metric",
            "resultado",
            "medir",
            "success",
        ),
    }
    for field_name, markers in line_map.items():
        if context.get(field_name):
            continue
        if any(marker in lowered for marker in markers):
            context[field_name] = founder_message.strip()

    issue_payload = youtrack_context.get("issue", {})
    if isinstance(issue_payload, dict):
        if not context.get(ContractField.OBJECTIVE.value) and issue_payload.get("summary"):
            context[ContractField.OBJECTIVE.value] = str(issue_payload["summary"])
        if not context.get(ContractField.SCOPE.value) and issue_payload.get("summary"):
            context[ContractField.SCOPE.value] = str(issue_payload["summary"])

    return context


def _find_missing_fields(contract_context: dict[str, Any]) -> list[str]:
    ordered_fields = [
        ContractField.OBJECTIVE.value,
        ContractField.CONSTRAINTS.value,
        ContractField.USER.value,
        ContractField.SCOPE.value,
        ContractField.EXPECTED_SUCCESS.value,
    ]
    return [
        field_name
        for field_name in ordered_fields
        if not str(contract_context.get(field_name, "")).strip()
    ]


def _build_brief_draft(
    thread: ConversationThread,
    *,
    contract_context: dict[str, Any],
    brief_version: int,
    timestamp: datetime,
    force_assumptions: bool,
) -> dict[str, Any]:
    missing_fields = _find_missing_fields(contract_context)
    assumptions = [
        _assumption_for_field(ContractField(field_name))
        for field_name in missing_fields
    ]
    constraints = _split_listish(contract_context.get(ContractField.CONSTRAINTS.value))
    if force_assumptions and assumptions:
        constraints.extend(assumptions)

    objective = str(contract_context.get(ContractField.OBJECTIVE.value, "")).strip()
    user = str(contract_context.get(ContractField.USER.value, "")).strip()
    scope = str(contract_context.get(ContractField.SCOPE.value, "")).strip()
    success = str(contract_context.get(ContractField.EXPECTED_SUCCESS.value, "")).strip()

    return {
        "issue_id": thread.issue_id,
        "project": thread.project,
        "objective": objective or f"Clarify and launch the initial scope for {thread.issue_id}.",
        "problem": (
            f"Founder wants to address: {objective or thread.topic}. "
            f"Primary user context: {user or 'pending definition'}."
        ).strip(),
        "expected_impact": success or "Founder validation of the first contractual brief.",
        "priority": "HIGH",
        "constraints": constraints or ["No restrictions were provided yet; confirm before execution."],
        "non_goals": _build_non_goals(scope),
        "kpis": [success] if success else ["Founder explicit approval of the draft brief."],
        "business_brief_status": "draft",
        "founder_approved": False,
        "summary": {
            "user": user or "pending definition",
            "scope": scope or "pending definition",
            "success": success or "pending definition",
        },
        "conversation_thread_id": thread.thread_id,
        "brief_version": brief_version,
        "created_at": timestamp.isoformat(),
    }


def _build_draft_message(
    *,
    brief_draft: dict[str, Any],
    missing_fields: list[str],
) -> str:
    summary = brief_draft["summary"]
    lines = [
        f"Preparé el `BusinessBrief` draft v{brief_draft['brief_version']}.",
        f"Objetivo: {brief_draft['objective']}",
        f"Usuario principal: {summary['user']}",
        f"Alcance inicial: {summary['scope']}",
        f"Éxito esperado: {summary['success']}",
    ]
    if missing_fields:
        lines.append("Incluí supuestos para los puntos todavía incompletos.")
    lines.append("Si estás de acuerdo, respondé: approve, approved, ok aprobar o confirmo.")
    return "\n".join(lines)


def _question_for_field(field_name: ContractField) -> str:
    questions = {
        ContractField.OBJECTIVE: "¿Cuál es el objetivo principal que querés lograr con esta iniciativa?",
        ContractField.CONSTRAINTS: (
            "¿Qué restricciones tenemos que respetar en esta primera versión? "
            "Tiempo, presupuesto, compliance, integraciones o cosas fuera de alcance."
        ),
        ContractField.USER: (
            "¿Quién es el usuario principal del primer release? "
            "Por ejemplo pacientes, recepcionistas, médicos, admins u otro perfil."
        ),
        ContractField.SCOPE: (
            "¿Qué alcance exacto querés para el MVP? "
            "Decime 1 a 3 capacidades concretas que sí deben entrar."
        ),
        ContractField.EXPECTED_SUCCESS: (
            "¿Cómo se ve el éxito esperado? "
            "Puede ser una métrica, una validación operativa o un resultado concreto."
        ),
    }
    return questions[field_name]


def _format_questions(questions: list[str]) -> str:
    lines = ["Necesito aclarar:"]
    lines.extend(f"{index}. {question}" for index, question in enumerate(questions, start=1))
    return "\n".join(lines)


def _extract_answer_lines(founder_message: str) -> list[str]:
    numbered_matches = re.findall(r"(?:^|\n)\s*\d+[.)-]?\s*(.+)", founder_message)
    if numbered_matches:
        return [match.strip() for match in numbered_matches if match.strip()]
    lines = [line.strip(" -\t") for line in founder_message.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines
    semicolon_parts = [part.strip() for part in founder_message.split(";") if part.strip()]
    if len(semicolon_parts) > 1:
        return semicolon_parts
    stripped = founder_message.strip()
    return [stripped] if stripped else []


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _split_listish(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    parts = re.split(r"[;\n,]", text)
    normalized = [part.strip(" -\t") for part in parts if part.strip(" -\t")]
    return normalized or [text]


def _build_non_goals(scope: str) -> list[str]:
    if scope.strip():
        return [
            "No expandir el alcance fuera del MVP definido por Founder y PM.",
            "No iniciar implementación técnica antes de aprobación explícita.",
        ]
    return [
        "No ejecutar sin alcance explícito aprobado.",
        "No asumir features avanzadas fuera del primer draft.",
    ]


def _assumption_for_field(field_name: ContractField) -> str:
    assumptions = {
        ContractField.OBJECTIVE: "Asumir objetivo inicial del founder hasta nueva aclaración.",
        ContractField.CONSTRAINTS: "Asumir restricciones conservadoras y sin auto-aprobación.",
        ContractField.USER: "Asumir usuario principal por definir antes del handoff técnico.",
        ContractField.SCOPE: "Asumir MVP acotado y sin expansión de alcance.",
        ContractField.EXPECTED_SUCCESS: "Asumir éxito inicial medido por validación del founder.",
    }
    return assumptions[field_name]


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
