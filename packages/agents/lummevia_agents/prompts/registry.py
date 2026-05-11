from __future__ import annotations

from lummevia_core import AgentRole

from lummevia_agents.prompts.exceptions import PromptTemplateNotFoundError
from lummevia_agents.prompts.templates import PromptTemplate, build_default_templates


class PromptRegistry:
    def __init__(self, templates: list[PromptTemplate] | None = None) -> None:
        self._templates: dict[tuple[AgentRole, str], PromptTemplate] = {}
        for template in templates or []:
            self.register(template)

    @classmethod
    def default(cls) -> "PromptRegistry":
        return cls(build_default_templates())

    def register(self, template: PromptTemplate) -> None:
        self._templates[(template.role, template.target_artifact)] = template

    def get_template(self, role: AgentRole, target_artifact: str) -> PromptTemplate:
        template = self._templates.get((role, target_artifact))
        if template is None:
            raise PromptTemplateNotFoundError(
                "No prompt template registered for role "
                f"'{role.value}' and target artifact '{target_artifact}'."
            )
        return template

    def get_template_by_id(self, template_id: str) -> PromptTemplate:
        for template in self._templates.values():
            if template.template_id == template_id:
                return template

        raise PromptTemplateNotFoundError(
            f"No prompt template registered with template_id '{template_id}'."
        )
