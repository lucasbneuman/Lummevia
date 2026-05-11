from __future__ import annotations

from lummevia_core import AgentRole

from lummevia_agents.prompts.exceptions import PromptTemplateNotFoundError
from lummevia_agents.prompts.templates import PromptTemplate, build_default_templates


class PromptRegistry:
    def __init__(
        self,
        templates: list[PromptTemplate] | None = None,
        *,
        baseline_registry=None,
    ) -> None:
        if baseline_registry is None:
            from lummevia_evaluations.baselines import PromptBaselineRegistry

            baseline_registry = PromptBaselineRegistry.default()

        self._baseline_registry = baseline_registry
        self._route_to_template_id: dict[tuple[AgentRole, str], str] = {}
        self._templates_by_id: dict[str, dict[str, PromptTemplate]] = {}
        self._registration_order: dict[str, list[str]] = {}
        for template in templates or []:
            self.register(template)

    @classmethod
    def default(cls) -> "PromptRegistry":
        return cls(build_default_templates())

    def register(self, template: PromptTemplate) -> None:
        self._route_to_template_id[(template.role, template.target_artifact)] = (
            template.template_id
        )
        versions = self._templates_by_id.setdefault(template.template_id, {})
        versions[template.version] = template
        registration_order = self._registration_order.setdefault(template.template_id, [])
        if template.version not in registration_order:
            registration_order.append(template.version)

    def get_template(
        self,
        role: AgentRole,
        target_artifact: str,
        *,
        version: str | None = None,
    ) -> PromptTemplate:
        template_id = self._route_to_template_id.get((role, target_artifact))
        if template_id is None:
            raise PromptTemplateNotFoundError(
                "No prompt template registered for role "
                f"'{role.value}' and target artifact '{target_artifact}'."
            )
        return self.get_template_by_id(template_id, version=version)

    def get_template_by_id(
        self,
        template_id: str,
        *,
        version: str | None = None,
    ) -> PromptTemplate:
        versions = self._templates_by_id.get(template_id)
        if versions is None:
            raise PromptTemplateNotFoundError(
                f"No prompt template registered with template_id '{template_id}'."
            )

        resolved_version = self._resolve_version(template_id, requested_version=version)
        template = versions.get(resolved_version)
        if template is None:
            raise PromptTemplateNotFoundError(
                "No prompt template registered with template_id "
                f"'{template_id}' and version '{resolved_version}'."
            )
        return template

    def _resolve_version(
        self,
        template_id: str,
        *,
        requested_version: str | None,
    ) -> str:
        if requested_version is not None:
            return requested_version

        active_version = self._baseline_registry.get_active_version(template_id)
        if active_version is not None:
            return active_version

        registration_order = self._registration_order.get(template_id, [])
        if not registration_order:
            raise PromptTemplateNotFoundError(
                f"No prompt template registered with template_id '{template_id}'."
            )
        return registration_order[-1]
