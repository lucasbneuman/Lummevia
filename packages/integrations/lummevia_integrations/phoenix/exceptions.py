class PhoenixIntegrationError(Exception):
    """Base exception for Phoenix integration placeholders."""


class PhoenixIntegrationNotImplementedError(PhoenixIntegrationError):
    """Raised when a Phoenix operation is requested before real integration exists."""
