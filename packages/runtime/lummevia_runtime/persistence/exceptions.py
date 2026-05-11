class PersistenceError(Exception):
    """Base exception for runtime persistence errors."""


class PersistedRunNotFoundError(PersistenceError):
    """Raised when a persisted workflow run cannot be found."""
