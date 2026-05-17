"""
Notion connector — fetches pages and databases from Notion.

Phase: 5  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 5 (Connectors)

TODO (Phase 5):
    pip install notion-client
    from notion_client import AsyncClient
    client = AsyncClient(auth=self.token)
    pages = await client.search(filter={"property": "object", "value": "page"})
"""

from __future__ import annotations
from docnest.connectors.base import IConnector
from docnest.models import RawDocument
from docnest.exceptions import ConnectorError


class NotionConnector(IConnector):
    """Fetches pages and database entries from a Notion workspace."""

    def __init__(self, token: str, page_id: str | None = None) -> None:
        self.token = token
        self.page_id = page_id  # None = fetch all accessible pages

    @property
    def name(self) -> str:
        return "Notion"

    def validate_config(self) -> None:
        if not self.token:
            raise ConnectorError("Notion integration token is required.")

    async def fetch(self) -> list[RawDocument]:
        # TODO (Phase 5): Implement using notion-client
        raise NotImplementedError("NotionConnector not yet implemented.")
