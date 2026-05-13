from __future__ import annotations

from lummevia_strategy.schemas import QALevel, RiskLevel, SandboxLevel


DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.55
DEFAULT_HIGH_DIFF_THRESHOLD = 8
DEFAULT_RECOVERY_RETRY_THRESHOLD = 2

RISK_WEIGHTS = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}

QA_WEIGHTS = {
    QALevel.BASIC: 0,
    QALevel.STANDARD: 1,
    QALevel.STRICT: 2,
    QALevel.PARANOID: 3,
}

SANDBOX_WEIGHTS = {
    SandboxLevel.NONE: 0,
    SandboxLevel.BASIC: 1,
    SandboxLevel.ISOLATED: 2,
    SandboxLevel.STRICT: 3,
}
