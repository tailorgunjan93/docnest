"""
Confluence connector — fetches pages from an Atlassian Confluence space.

Phase: 5  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 5 (Connectors)

TODO (Phase 5):
    pip install atlassian-python-api
    from atlassian import Confluence
    confluence = Confluence(url=self.base_url, token=self.token)
    pages = confluence.get_all_pages_from_space(self.space_key)
"""

from __future__ import annotations
from docnest.connectors.base import IConnector
from docnest.models import RawDocument
from docnest.exceptions import ConnectorError


class ConfluenceConnector(IConnector):
    """Fetches pages and child pages from a Confluence space.

    Preserves page hierarchy as section parent/child relationships.
    Tables in Confluence pages are preserved as TableData objects.
    """

    def __init__(self, base_url: str, token: str, space_key: str) -> None:
        self.base_url = base_url
        self.token = token
        self.space_key = space_key

    @property
    def name(self) -> str:
        return "Confluence"

    def validate_config(self) -> None:
        if not all([self.base_url, self.token, self.space_key]):
            raise ConnectorError("base_url, token, and space_key are required.")

    async def fetch(self) -> list[RawDocument]:
        # TODO (Phase 5): Implement using atlassian-python-api
        raise NotImplementedError("ConfluenceConnector not yet implemented.")
