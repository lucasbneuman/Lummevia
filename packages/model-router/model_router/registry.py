from model_router.exceptions import UnknownRoleError
from model_router.schemas import AgentRole, ModelConfig, Provider


DEFAULT_ROLE_CONFIGS: dict[AgentRole, ModelConfig | None] = {
    AgentRole.PM: ModelConfig(
        provider=Provider.OPENROUTER,
        model="deepseek/deepseek-chat",
        temperature=0.1,
        max_tokens=4096,
    ),
    AgentRole.PO: ModelConfig(
        provider=Provider.OPENROUTER,
        model="deepseek/deepseek-chat",
        temperature=0.15,
        max_tokens=4096,
    ),
    AgentRole.DEV: ModelConfig(
        provider=Provider.OPENROUTER,
        model="deepseek/deepseek-chat-lite",
        temperature=0.1,
        max_tokens=4096,
    ),
    AgentRole.QA: ModelConfig(
        provider=Provider.OPENROUTER,
        model="deepseek/deepseek-chat-lite",
        temperature=0.1,
        max_tokens=3072,
    ),
    AgentRole.QC: ModelConfig(
        provider=Provider.OPENROUTER,
        model="deepseek/deepseek-chat",
        temperature=0.05,
        max_tokens=4096,
    ),
}

ENVIRONMENT_ROLE_CONFIGS: dict[str, dict[AgentRole, ModelConfig]] = {
    "production": {
        AgentRole.QA: ModelConfig(
            provider=Provider.OPENROUTER,
            model="deepseek/deepseek-chat",
            temperature=0.05,
            max_tokens=4096,
        )
    }
}

PROJECT_ROLE_CONFIGS: dict[str, dict[AgentRole, ModelConfig]] = {
    "lummevia-os": {
        AgentRole.DEV: ModelConfig(
            provider=Provider.OPENROUTER,
            model="deepseek/deepseek-chat-lite",
            temperature=0.05,
            max_tokens=6144,
        )
    }
}

PROJECT_ENVIRONMENT_ROLE_CONFIGS: dict[tuple[str, str], dict[AgentRole, ModelConfig]] = {
    ("lummevia-os", "production"): {
        AgentRole.PM: ModelConfig(
            provider=Provider.OPENROUTER,
            model="deepseek/deepseek-chat-pro",
            temperature=0.1,
            max_tokens=6144,
        )
    }
}


def normalize_scope(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    return normalized or None


def get_model_config(
    role: AgentRole,
    project: str | None = None,
    environment: str | None = None,
) -> tuple[ModelConfig, str]:
    normalized_project = normalize_scope(project)
    normalized_environment = normalize_scope(environment)

    if normalized_project and normalized_environment:
        config = PROJECT_ENVIRONMENT_ROLE_CONFIGS.get(
            (normalized_project, normalized_environment),
            {},
        ).get(role)
        if config is not None:
            return config, "project_environment"

    if normalized_project:
        config = PROJECT_ROLE_CONFIGS.get(normalized_project, {}).get(role)
        if config is not None:
            return config, "project"

    if normalized_environment:
        config = ENVIRONMENT_ROLE_CONFIGS.get(normalized_environment, {}).get(role)
        if config is not None:
            return config, "environment"

    config = DEFAULT_ROLE_CONFIGS.get(role)
    if config is None:
        raise UnknownRoleError(f"No model configuration registered for role '{role.value}'.")

    return config, "default"
