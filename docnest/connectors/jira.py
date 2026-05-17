"""
Jira connector — fetches issues, epics, and comments from a Jira project.

Phase: 5  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 5 (Connectors)

TODO (Phase 5):
    pip install atlassian-python-api
    from atlassian import Jira
    jira = Jira(url=self.base_url, token=self.token)
    issues = jira.get_all_issues_for_project(self.project_key)
"""

from __future__ import annotations
from docnest.connectors.base import IConnector
from docnest.models import RawDocument
from docnest.exceptions import ConnectorError


class JiraConnector(IConnector):
    """Fetches issues, epics, and comments from a Jira project."""

    def __init__(self, base_url: str, token: str, project_key: str) -> None:
        self.base_url = base_url
        self.token = token
        self.project_key = project_key

    @property
    def name(self) -> str:
        return "Jira"

    def validate_config(self) -> None:
        if not all([self.base_url, self.token, self.project_key]):
            raise ConnectorError("base_url, token, and project_key are required.")

    async def fetch(self) -> list[RawDocument]:
        # TODO (Phase 5): Implement using atlassian-python-api
        raise NotImplementedError("JiraConnector not yet implemented.")
