class GitHubIntegrationError(Exception):
    """Base exception for GitHub integration placeholders."""


class GitHubIntegrationNotImplementedError(GitHubIntegrationError):
    """Raised when a GitHub operation is requested before real integration exists."""
