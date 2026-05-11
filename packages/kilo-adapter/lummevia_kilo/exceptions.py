class KiloAdapterError(Exception):
    """Base exception for Kilo adapter skeleton errors."""


class UnsupportedKiloRoleError(KiloAdapterError):
    """Raised when a runtime role has no Kilo mode mapping."""
