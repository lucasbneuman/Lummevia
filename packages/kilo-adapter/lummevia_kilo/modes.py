from __future__ import annotations

from enum import Enum

from lummevia_core import AgentRole

from lummevia_kilo.exceptions import UnsupportedKiloRoleError


class KiloExecutionMode(str, Enum):
    ASK = "ASK"
    PLAN = "PLAN"
    CODE = "CODE"
    DEBUG = "DEBUG"
    ORCHESTRATOR = "ORCHESTRATOR"


ROLE_TO_KILO_MODE: dict[AgentRole, KiloExecutionMode] = {
    AgentRole.PO: KiloExecutionMode.PLAN,
    AgentRole.DEV: KiloExecutionMode.CODE,
    AgentRole.QA: KiloExecutionMode.DEBUG,
}


def resolve_kilo_mode(role: AgentRole) -> KiloExecutionMode:
    try:
        return ROLE_TO_KILO_MODE[role]
    except KeyError as exc:
        raise UnsupportedKiloRoleError(
            f"Role '{role.value}' does not have a Kilo execution mode mapping."
        ) from exc
