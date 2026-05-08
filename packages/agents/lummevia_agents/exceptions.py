class AgentError(Exception):
    """Base exception for Lummevia agent placeholders."""


class AgentNotImplementedError(AgentError):
    """Raised when an agent runtime is requested before workflows exist."""
