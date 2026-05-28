from __future__ import annotations

from typing import Any

import httpx

from lummevia_integrations.youtrack.exceptions import (
    YouTrackConfigurationError,
    YouTrackIntegrationError,
)
from lummevia_integrations.youtrack.schemas import (
    AgentContextBundle,
    KnowledgeDocumentRef,
    OperationalIssueRef,
    ProjectContextSource,
    ProjectContextSourceType,
    YouTrackArtifactLink,
    YouTrackBugPayload,
    YouTrackComment,
    YouTrackCommentPayload,
    YouTrackIssue,
    YouTrackIssueCreatePayload,
    YouTrackIssueCustomField,
    YouTrackIssueUpdatePayload,
    YouTrackKnowledgeDocument,
    YouTrackKnowledgeDocumentUpsertPayload,
    YouTrackProject,
)

ISSUE_FIELDS = (
    "id,idReadable,summary,description,"
    "project(shortName),"
    "customFields(name,value(name,login,fullName,text,presentation)),"
    "tags(name)"
)
COMMENT_FIELDS = "id,text"
ARTICLE_FIELDS = "id,idReadable,summary,content,project(shortName),parentArticle(id),tags(name)"
PROJECT_FIELDS = "id,name,shortName,archived"


class YouTrackClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        enabled: bool | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        normalized_base_url = self._normalize_base_url(base_url)
        normalized_token = token.strip() if token is not None else None
        if normalized_token == "":
            normalized_token = None

        self.base_url = normalized_base_url
        self.token = normalized_token
        self.enabled = (
            enabled
            if enabled is not None
            else bool(self.base_url is not None and self.token is not None)
        )
        self._client = httpx.Client(
            base_url=self.base_url or "https://invalid.youtrack.local/api",
            headers=self._build_headers(self.token),
            transport=transport,
            timeout=timeout_seconds,
        )

    @staticmethod
    def _normalize_base_url(base_url: str | None) -> str | None:
        if base_url is None:
            return None
        stripped = base_url.strip().rstrip("/")
        if not stripped:
            return None
        if stripped.endswith("/api"):
            return stripped
        return f"{stripped}/api"

    @staticmethod
    def _build_headers(token: str | None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    @property
    def is_configured(self) -> bool:
        return self.enabled and self.base_url is not None and self.token is not None

    def _ensure_configured(self) -> None:
        if self.is_configured:
            return
        raise YouTrackConfigurationError(
            "YouTrack integration requires YOUTRACK_BASE_URL and YOUTRACK_TOKEN."
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        self._ensure_configured()
        try:
            response = self._client.request(method, path, params=params, json=json)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            raise YouTrackIntegrationError(
                f"YouTrack request failed with status {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise YouTrackIntegrationError(
                f"YouTrack request failed: {exc}"
            ) from exc

        if not response.content:
            return None
        return response.json()

    def _issue_url(self, id_readable: str | None) -> str | None:
        if self.base_url is None or id_readable is None:
            return None
        return self.base_url.removesuffix("/api") + f"/issue/{id_readable}"

    def _article_url(self, id_readable: str | None) -> str | None:
        if self.base_url is None or id_readable is None:
            return None
        return self.base_url.removesuffix("/api") + f"/articles/{id_readable}"

    @staticmethod
    def _parse_custom_field_value(value: Any) -> Any:
        if isinstance(value, dict):
            for candidate in ("name", "presentation", "text", "fullName", "login"):
                if candidate in value and value[candidate] is not None:
                    return value[candidate]
            return value
        if isinstance(value, list):
            return [YouTrackClient._parse_custom_field_value(item) for item in value]
        return value

    def _parse_issue(self, payload: dict[str, Any]) -> YouTrackIssue:
        project_payload = payload.get("project") or {}
        custom_fields_payload = payload.get("customFields") or []
        custom_fields = [
            YouTrackIssueCustomField(
                name=str(field.get("name", "")),
                value=self._parse_custom_field_value(field.get("value")),
            )
            for field in custom_fields_payload
            if str(field.get("name", "")).strip()
        ]
        state_value = next(
            (
                field.value
                for field in custom_fields
                if field.name.casefold() == "state"
            ),
            None,
        )
        tag_payload = payload.get("tags") or []
        issue_data = {
            "id": payload.get("id"),
            "issue_id": payload.get("idReadable") or payload.get("id") or "UNKNOWN",
            "project": project_payload.get("shortName") or "UNKNOWN",
            "summary": payload.get("summary") or "Untitled issue",
            "description": payload.get("description"),
            "state": state_value if isinstance(state_value, str) else None,
            "custom_fields": custom_fields,
            "tags": [
                str(tag.get("name", "")).strip()
                for tag in tag_payload
                if str(tag.get("name", "")).strip()
            ],
            "links": [],
            "metadata": {
                key: value
                for key, value in payload.items()
                if key not in {"id", "idReadable", "summary", "description", "project", "customFields", "tags"}
            },
        }
        issue_url = self._issue_url(payload.get("idReadable"))
        if issue_url is not None:
            issue_data["url"] = issue_url
        return YouTrackIssue.model_validate(issue_data)

    def _parse_comment(self, issue_id: str, payload: dict[str, Any]) -> YouTrackComment:
        comment_data = {
            "comment_id": payload.get("id"),
            "issue_id": issue_id,
            "body": payload.get("text") or payload.get("body") or "",
            "metadata": {
                key: value
                for key, value in payload.items()
                if key not in {"id", "text", "body"}
            },
        }
        if payload.get("id") is not None:
            comment_data["url"] = (
                self._issue_url(issue_id) + f"#focus=Comments-{payload['id']}"
                if self._issue_url(issue_id) is not None
                else None
            )
        return YouTrackComment.model_validate(comment_data)

    def _parse_article(self, payload: dict[str, Any]) -> YouTrackKnowledgeDocument:
        project_payload = payload.get("project") or {}
        parent_payload = payload.get("parentArticle") or {}
        tag_payload = payload.get("tags") or []
        article_data = {
            "document_id": payload.get("id") or "UNKNOWN",
            "id_readable": payload.get("idReadable"),
            "project": project_payload.get("shortName") or "UNKNOWN",
            "title": payload.get("summary") or "Untitled article",
            "content": payload.get("content"),
            "parent_document_id": parent_payload.get("id"),
            "tags": [
                str(tag.get("name", "")).strip()
                for tag in tag_payload
                if str(tag.get("name", "")).strip()
            ],
            "metadata": {
                key: value
                for key, value in payload.items()
                if key not in {"id", "idReadable", "summary", "content", "project", "parentArticle", "tags"}
            },
        }
        article_url = self._article_url(payload.get("idReadable"))
        if article_url is not None:
            article_data["url"] = article_url
        return YouTrackKnowledgeDocument.model_validate(article_data)

    def _parse_project(self, payload: dict[str, Any]) -> YouTrackProject:
        short_name = payload.get("shortName") or payload.get("short_name") or payload.get("id")
        name = payload.get("name") or short_name or "Unknown project"
        return YouTrackProject.model_validate(
            {
                "id": payload.get("id"),
                "short_name": short_name or "UNKNOWN",
                "name": name,
                "archived": bool(payload.get("archived", False)),
                "metadata": {
                    key: value
                    for key, value in payload.items()
                    if key not in {"id", "name", "shortName", "short_name", "archived"}
                },
            }
        )

    @staticmethod
    def _build_issue_custom_fields(
        payload: YouTrackIssueUpdatePayload | YouTrackIssueCreatePayload,
    ) -> list[dict[str, Any]]:
        custom_fields: list[dict[str, Any]] = []
        for name, value in payload.custom_fields.items():
            custom_fields.append({"name": name, "value": value})
        if isinstance(payload, YouTrackIssueUpdatePayload) and payload.state is not None:
            custom_fields.append({"name": "State", "value": {"name": payload.state}})
        return custom_fields

    def get_issue(self, issue_id: str) -> YouTrackIssue:
        payload = self._request(
            "GET",
            f"/issues/{issue_id}",
            params={"fields": ISSUE_FIELDS},
        )
        return self._parse_issue(payload)

    def search_issues(
        self,
        *,
        project: str,
        query: str | None = None,
        limit: int = 20,
    ) -> list[YouTrackIssue]:
        query_parts = [f"project: {project}"]
        if query is not None and query.strip():
            query_parts.append(query.strip())
        payload = self._request(
            "GET",
            "/issues",
            params={
                "fields": ISSUE_FIELDS,
                "$top": limit,
                "query": " ".join(query_parts),
            },
        )
        return [self._parse_issue(item) for item in payload or []]

    def list_projects(
        self,
        *,
        include_archived: bool = False,
        limit: int = 100,
    ) -> list[YouTrackProject]:
        payload = self._request(
            "GET",
            "/admin/projects",
            params={
                "fields": PROJECT_FIELDS,
                "$top": limit,
            },
        )
        projects = [self._parse_project(item) for item in payload or []]
        if include_archived:
            return projects
        return [project for project in projects if not project.archived]

    def add_comment(self, issue_id: str, payload: YouTrackCommentPayload) -> YouTrackComment:
        comment_payload = self._request(
            "POST",
            f"/issues/{issue_id}/comments",
            params={"fields": COMMENT_FIELDS},
            json={"text": payload.body},
        )
        return self._parse_comment(issue_id, comment_payload)

    def create_issue(self, payload: YouTrackIssueCreatePayload) -> YouTrackIssue:
        body: dict[str, Any] = {
            "summary": payload.summary,
            "description": payload.description,
            "project": {"shortName": payload.project},
        }
        custom_fields = self._build_issue_custom_fields(payload)
        if custom_fields:
            body["customFields"] = custom_fields
        created = self._request(
            "POST",
            "/issues",
            params={"fields": ISSUE_FIELDS},
            json=body,
        )
        issue = self._parse_issue(created)
        if payload.tags:
            issue = issue.model_copy(update={"tags": payload.tags})
        return issue

    def update_issue(self, issue_id: str, payload: YouTrackIssueUpdatePayload) -> YouTrackIssue:
        body: dict[str, Any] = {}
        if payload.summary is not None:
            body["summary"] = payload.summary
        if payload.description is not None:
            body["description"] = payload.description
        custom_fields = self._build_issue_custom_fields(payload)
        if custom_fields:
            body["customFields"] = custom_fields
        updated = self._request(
            "POST",
            f"/issues/{issue_id}",
            params={"fields": ISSUE_FIELDS},
            json=body,
        )
        return self._parse_issue(updated)

    def create_bug(self, payload: YouTrackBugPayload) -> YouTrackIssue:
        description_lines = [payload.description]
        if payload.steps_to_reproduce:
            description_lines.append("Steps to reproduce:")
            description_lines.extend(f"- {step}" for step in payload.steps_to_reproduce)
        if payload.related_issue_id:
            description_lines.append(f"Related issue: {payload.related_issue_id}")
        if payload.expected_behavior:
            description_lines.append(f"Expected behavior: {payload.expected_behavior}")
        if payload.actual_behavior:
            description_lines.append(f"Actual behavior: {payload.actual_behavior}")
        created = self.create_issue(
            YouTrackIssueCreatePayload(
                project=payload.project,
                summary=payload.summary,
                description="\n".join(description_lines),
                parent_issue_id=payload.related_issue_id,
                custom_fields={"Type": {"name": "Bug"}},
            )
        )
        return created

    def link_artifact(self, issue_id: str, artifact_link: YouTrackArtifactLink) -> YouTrackComment:
        body = (
            f"[Artifact] {artifact_link.artifact_type} - {artifact_link.title}\n"
            f"artifact_id: {artifact_link.artifact_id}"
        )
        if artifact_link.url is not None:
            body += f"\nurl: {artifact_link.url}"
        return self.add_comment(issue_id, YouTrackCommentPayload(body=body))

    def list_knowledge_documents(
        self,
        *,
        project: str,
        query: str | None = None,
        limit: int = 20,
    ) -> list[YouTrackKnowledgeDocument]:
        payload = self._request(
            "GET",
            "/articles",
            params={
                "fields": ARTICLE_FIELDS,
                "$top": limit,
            },
        )
        documents = [self._parse_article(item) for item in payload or []]
        filtered = [document for document in documents if document.project == project]
        if query is None or not query.strip():
            return filtered
        normalized_query = query.casefold()
        return [
            document
            for document in filtered
            if normalized_query in document.title.casefold()
            or normalized_query in (document.content or "").casefold()
            or any(normalized_query in tag.casefold() for tag in document.tags)
        ]

    def get_knowledge_document(self, document_id: str) -> YouTrackKnowledgeDocument:
        payload = self._request(
            "GET",
            f"/articles/{document_id}",
            params={"fields": ARTICLE_FIELDS},
        )
        return self._parse_article(payload)

    def upsert_knowledge_document(
        self,
        payload: YouTrackKnowledgeDocumentUpsertPayload,
    ) -> YouTrackKnowledgeDocument:
        body: dict[str, Any] = {
            "summary": payload.title,
            "content": payload.content,
            "project": {"shortName": payload.project},
        }
        if payload.parent_document_id is not None:
            body["parentArticle"] = {"id": payload.parent_document_id}
        path = "/articles"
        if payload.document_id is not None:
            path = f"/articles/{payload.document_id}"
        document_payload = self._request(
            "POST",
            path,
            params={"fields": ARTICLE_FIELDS},
            json=body,
        )
        document = self._parse_article(document_payload)
        if payload.tags:
            document = document.model_copy(update={"tags": payload.tags})
        return document

    def get_agent_context(
        self,
        *,
        project: str,
        role: str,
        issue_id: str | None = None,
        issue_query: str | None = None,
    ) -> AgentContextBundle:
        issue_ref: OperationalIssueRef | None = None
        related_issues: list[OperationalIssueRef] = []
        sources: list[ProjectContextSource] = []

        if issue_id is not None:
            issue = self.get_issue(issue_id)
            issue_ref = OperationalIssueRef(
                issue_id=issue.issue_id,
                project=issue.project,
                summary=issue.summary,
                state=issue.state,
                url=issue.url,
            )
            sources.append(
                ProjectContextSource(
                    source_type=ProjectContextSourceType.ISSUE,
                    source_id=issue.issue_id,
                    title=issue.summary,
                    url=issue.url,
                    required=True,
                    role=role,
                )
            )
        if issue_query is not None and issue_query.strip():
            related_issues = [
                OperationalIssueRef(
                    issue_id=issue.issue_id,
                    project=issue.project,
                    summary=issue.summary,
                    state=issue.state,
                    url=issue.url,
                )
                for issue in self.search_issues(
                    project=project,
                    query=issue_query,
                    limit=10,
                )
                if issue_id is None or issue.issue_id != issue_id
            ]

        documents = self.list_knowledge_documents(project=project, limit=25)
        selected_documents = _select_documents_for_role(documents, role=role)
        document_refs = [
            KnowledgeDocumentRef(
                document_id=document.document_id,
                project=document.project,
                title=document.title,
                url=document.url,
                summary=_truncate_text(document.content),
            )
            for document in selected_documents
        ]
        for document in selected_documents:
            sources.append(
                ProjectContextSource(
                    source_type=ProjectContextSourceType.KNOWLEDGE_BASE,
                    source_id=document.document_id,
                    title=document.title,
                    url=document.url,
                    required=_document_is_required(document, role=role),
                    role=role,
                )
            )

        artifact_links = []
        if issue_ref is not None:
            artifact_links.append(
                YouTrackArtifactLink(
                    artifact_type="OperationalIssue",
                    artifact_id=issue_ref.issue_id,
                    title=issue_ref.summary or issue_ref.issue_id,
                    url=issue_ref.url,
                )
            )

        return AgentContextBundle(
            project=project,
            role=role,
            issue=issue_ref,
            related_issues=related_issues,
            knowledge_documents=document_refs,
            sources=sources,
            artifact_links=artifact_links,
            metadata={
                "issue_query": issue_query,
                "knowledge_document_count": len(document_refs),
                "related_issue_count": len(related_issues),
            },
        )

def _truncate_text(value: str | None, *, limit: int = 160) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _document_is_required(document: YouTrackKnowledgeDocument, *, role: str) -> bool:
    normalized_role = role.casefold()
    haystacks = [document.title.casefold(), (document.content or "").casefold()]
    role_markers = {
        "pm": ("pm", "product manager", "business brief", "workflow"),
        "po": ("po", "product owner", "execution package", "task package", "task plan"),
    }
    markers = role_markers.get(normalized_role, (normalized_role,))
    return any(any(marker in haystack for marker in markers) for haystack in haystacks)


def _select_documents_for_role(
    documents: list[YouTrackKnowledgeDocument],
    *,
    role: str,
    limit: int = 8,
) -> list[YouTrackKnowledgeDocument]:
    normalized_role = role.casefold()
    scored: list[tuple[int, YouTrackKnowledgeDocument]] = []
    for document in documents:
        title = document.title.casefold()
        content = (document.content or "").casefold()
        tags = [tag.casefold() for tag in document.tags]
        score = 0
        if normalized_role in title or normalized_role in content or normalized_role in tags:
            score += 3
        if any(keyword in title for keyword in ("workflow", "brief", "task", "policy", "sop")):
            score += 2
        if any(keyword in content for keyword in ("workflow", "brief", "task", "policy", "sop")):
            score += 1
        if score > 0:
            scored.append((score, document))

    if not scored:
        return documents[:limit]

    return [
        document
        for _, document in sorted(
            scored,
            key=lambda item: (-item[0], item[1].title.casefold()),
        )[:limit]
    ]
