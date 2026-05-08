class YouTrackIntegrationError(Exception):
    """Base exception for YouTrack integration placeholders."""


class YouTrackIntegrationNotImplementedError(YouTrackIntegrationError):
    """Raised when a YouTrack operation is requested before real integration exists."""
