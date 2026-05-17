"""
GitHub connector — fetches READMEs, wikis, issues, and markdown files from repos.

Phase: 5  |  Spec: docs/SPEC_DOCFORGE_PYPI.md — Section 5 (Connectors)

TODO (Phase 5):
    pip install PyGithub
    from github import Github
    gh = Github(self.token)
    repo = gh.get_repo(self.repo)
    for f in repo.get_contents(""):
        if f.name.endswith((".md", ".rst", ".txt")):
            yield RawDocument(source=f.html_url, ...)
"""

from __future__ import annotations
from docforge.connectors.base import IConnector
from docforge.models import RawDocument
from docforge.exceptions import ConnectorError


class GitHubConnector(IConnector):
    """Fetches markdown and text files from a GitHub repository.

    Supports:
        - READMEs and all .md files
        - GitHub Wiki pages
        - Issue bodies and comments (optional)
        - Pull request descriptions (optional)

    Usage:
        connector = GitHubConnector(token="ghp_...", repo="org/repo")
        docs = await connector.fetch()
    """

    def __init__(
        self,
        token: str,
        repo: str,
        include_issues: bool = False,
        include_prs: bool = False,
    ) -> None:
        self.token = token
        self.repo = repo
        self.include_issues = include_issues
        self.include_prs = include_prs

    @property
    def name(self) -> str:
        return "GitHub"

    def validate_config(self) -> None:
        if not self.token:
            raise ConnectorError("GitHub token is required.")
        if not self.repo or "/" not in self.repo:
            raise ConnectorError("repo must be in 'owner/name' format.")

    async def fetch(self) -> list[RawDocument]:
        # TODO (Phase 5): Implement using PyGithub
        raise NotImplementedError("GitHubConnector not yet implemented.")
