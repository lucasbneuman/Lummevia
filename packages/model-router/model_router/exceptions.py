class ModelRouterError(Exception):
    """Base exception for model router errors."""


class UnknownRoleError(ModelRouterError):
    """Raised when a role cannot be resolved from the registry."""


class InvalidEnvironmentOverrideError(ModelRouterError):
    """Raised when an environment override cannot be parsed."""
