class YouTrackIntegrationError(Exception):
    """Base exception for YouTrack integration failures."""


class YouTrackIntegrationNotImplementedError(YouTrackIntegrationError):
    """Raised when a YouTrack operation is requested before real integration exists."""


class YouTrackConfigurationError(YouTrackIntegrationError):
    """Raised when the YouTrack client lacks the required runtime configuration."""
