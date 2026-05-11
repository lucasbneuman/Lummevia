class RuntimeErrorBase(Exception):
    """Base exception for runtime orchestration errors."""


class RuntimeNotFoundError(RuntimeErrorBase):
    """Raised when a workflow run cannot be found in the in-memory registry."""
