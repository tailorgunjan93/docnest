"""Tests for docnest connectors — validate_config and basic construction.

Run: pytest tests/test_connectors.py -v
"""
from __future__ import annotations

import pytest

from docnest.exceptions import ConnectorError


# ── GitHubConnector ───────────────────────────────────────────────────────────

class TestGitHubConnector:
    def _make(self, token: str = "ghp_test", repo: str = "owner/repo") -> object:
        from docnest.connectors.github import GitHubConnector
        return GitHubConnector(token=token, repo=repo)

    def test_name_is_github(self):
        from docnest.connectors.github import GitHubConnector
        c = GitHubConnector(token="t", repo="a/b")
        assert c.name == "GitHub"

    def test_validate_config_passes_with_valid_inputs(self):
        c = self._make(token="ghp_abc123", repo="org/repo-name")
        c.validate_config()  # no exception

    def test_validate_config_raises_on_missing_token(self):
        c = self._make(token="", repo="org/repo")
        with pytest.raises(ConnectorError):
            c.validate_config()

    def test_validate_config_raises_on_invalid_repo(self):
        c = self._make(token="ghp_abc", repo="noslash")
        with pytest.raises(ConnectorError):
            c.validate_config()

    def test_validate_config_raises_on_empty_repo(self):
        c = self._make(token="ghp_abc", repo="")
        with pytest.raises(ConnectorError):
            c.validate_config()

    def test_fetch_raises_not_implemented(self):
        import asyncio
        c = self._make()
        with pytest.raises(NotImplementedError):
            asyncio.run(c.fetch())

    def test_include_issues_default_false(self):
        from docnest.connectors.github import GitHubConnector
        c = GitHubConnector(token="t", repo="a/b")
        assert c.include_issues is False

    def test_include_prs_default_false(self):
        from docnest.connectors.github import GitHubConnector
        c = GitHubConnector(token="t", repo="a/b")
        assert c.include_prs is False


# ── ConfluenceConnector ───────────────────────────────────────────────────────

class TestConfluenceConnector:
    def _make(self, base_url: str = "https://myorg.atlassian.net",
              token: str = "tok", space: str = "ENG") -> object:
        from docnest.connectors.confluence import ConfluenceConnector
        return ConfluenceConnector(base_url=base_url, token=token, space_key=space)

    def test_name_is_confluence(self):
        c = self._make()
        assert c.name == "Confluence"

    def test_validate_config_passes_with_valid_inputs(self):
        c = self._make()
        c.validate_config()

    def test_validate_config_raises_on_missing_url(self):
        c = self._make(base_url="")
        with pytest.raises(ConnectorError):
            c.validate_config()

    def test_validate_config_raises_on_missing_token(self):
        c = self._make(token="")
        with pytest.raises(ConnectorError):
            c.validate_config()

    def test_validate_config_raises_on_missing_space(self):
        c = self._make(space="")
        with pytest.raises(ConnectorError):
            c.validate_config()

    def test_fetch_raises_not_implemented(self):
        import asyncio
        c = self._make()
        with pytest.raises(NotImplementedError):
            asyncio.run(c.fetch())


# ── NotionConnector ───────────────────────────────────────────────────────────

class TestNotionConnector:
    def _make(self, token: str = "secret_abc", page_id: str | None = None) -> object:
        from docnest.connectors.notion import NotionConnector
        return NotionConnector(token=token, page_id=page_id)

    def test_name_is_notion(self):
        c = self._make()
        assert c.name == "Notion"

    def test_validate_config_passes_with_valid_token(self):
        c = self._make(token="secret_abc")
        c.validate_config()  # no exception

    def test_validate_config_raises_on_missing_token(self):
        c = self._make(token="")
        with pytest.raises(ConnectorError):
            c.validate_config()

    def test_page_id_optional(self):
        c = self._make(page_id=None)
        c.validate_config()  # page_id is optional

    def test_fetch_raises_not_implemented(self):
        import asyncio
        c = self._make()
        with pytest.raises(NotImplementedError):
            asyncio.run(c.fetch())


# ── JiraConnector ─────────────────────────────────────────────────────────────

class TestJiraConnector:
    def _make(self, base_url: str = "https://org.atlassian.net",
              token: str = "tok", project: str = "ENG") -> object:
        from docnest.connectors.jira import JiraConnector
        return JiraConnector(base_url=base_url, token=token, project_key=project)

    def test_name_is_jira(self):
        c = self._make()
        assert c.name == "Jira"

    def test_validate_config_passes_with_valid_inputs(self):
        c = self._make()
        c.validate_config()

    def test_validate_config_raises_on_missing_url(self):
        c = self._make(base_url="")
        with pytest.raises(ConnectorError):
            c.validate_config()

    def test_validate_config_raises_on_missing_token(self):
        c = self._make(token="")
        with pytest.raises(ConnectorError):
            c.validate_config()

    def test_validate_config_raises_on_missing_project(self):
        c = self._make(project="")
        with pytest.raises(ConnectorError):
            c.validate_config()

    def test_fetch_raises_not_implemented(self):
        import asyncio
        c = self._make()
        with pytest.raises(NotImplementedError):
            asyncio.run(c.fetch())
