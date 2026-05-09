from lummevia_agents.exceptions import AgentError


class PromptPipelineError(AgentError):
    """Base exception for prompt pipeline failures."""


class PromptTemplateNotFoundError(PromptPipelineError):
    """Raised when no template matches the requested role and artifact."""
