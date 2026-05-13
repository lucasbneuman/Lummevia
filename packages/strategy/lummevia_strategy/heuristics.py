from __future__ import annotations

from lummevia_strategy.policies import QA_WEIGHTS, RISK_WEIGHTS, SANDBOX_WEIGHTS
from lummevia_strategy.schemas import (
    ExecutionStrategyContext,
    QALevel,
    RiskLevel,
    SandboxLevel,
    StrategyType,
)


def risk_rank(risk_level: RiskLevel | None) -> int:
    if risk_level is None:
        return -1
    return RISK_WEIGHTS[risk_level]


def qa_rank(qa_level: QALevel | None) -> int:
    if qa_level is None:
        return -1
    return QA_WEIGHTS[qa_level]


def sandbox_rank(sandbox_level: SandboxLevel | None) -> int:
    if sandbox_level is None:
        return -1
    return SANDBOX_WEIGHTS[sandbox_level]


def resolve_strategy_event(
    *,
    context: ExecutionStrategyContext,
    strategy_type: StrategyType,
    risk_level: RiskLevel,
    qa_level: QALevel,
    sandbox_level: SandboxLevel,
) -> str:
    if bool(context.metadata.get("manual_override", False)):
        return "STRATEGY_OVERRIDDEN"
    if (
        risk_rank(risk_level) > risk_rank(context.previous_risk_level)
        or qa_rank(qa_level) > qa_rank(_previous_qa_level(context))
        or sandbox_rank(sandbox_level) > sandbox_rank(_previous_sandbox_level(context))
    ):
        return "STRATEGY_ESCALATED"
    if (
        risk_rank(risk_level) < risk_rank(context.previous_risk_level)
        or qa_rank(qa_level) < qa_rank(_previous_qa_level(context))
        or sandbox_rank(sandbox_level) < sandbox_rank(_previous_sandbox_level(context))
    ):
        return "STRATEGY_DEGRADED"
    if context.previous_strategy_type is not None and context.previous_strategy_type != strategy_type:
        return "STRATEGY_SELECTED"
    return "STRATEGY_SELECTED"


def build_reasoning(reasons: list[str]) -> str:
    return " ".join(reason.strip() for reason in reasons if reason.strip())


def _previous_qa_level(context: ExecutionStrategyContext) -> QALevel | None:
    raw_value = context.metadata.get("previous_qa_level")
    return QALevel(raw_value) if isinstance(raw_value, str) and raw_value else None


def _previous_sandbox_level(context: ExecutionStrategyContext) -> SandboxLevel | None:
    raw_value = context.metadata.get("previous_sandbox_level")
    return SandboxLevel(raw_value) if isinstance(raw_value, str) and raw_value else None
