from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lummevia_kilo.schemas import KiloSafetyCheckResult


class KiloAdapterError(Exception):
    """Base exception for Kilo adapter skeleton errors."""


class UnsupportedKiloRoleError(KiloAdapterError):
    """Raised when a runtime role has no Kilo mode mapping."""


class KiloSafetyViolation(KiloAdapterError):
    """Raised when a real execution does not pass sandbox safety checks."""

    def __init__(self, result: KiloSafetyCheckResult) -> None:
        self.result = result
        super().__init__(result.reason or "Kilo sandbox safety validation failed.")
