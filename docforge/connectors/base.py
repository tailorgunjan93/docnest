"""
Abstract base class for all DocForge source connectors.

Connectors fetch documents from external sources and return RawDocument
objects that feed directly into the DocForgePipeline.

Phase: 5  |  Spec: docs/SPEC_DOCFORGE_PYPI.md — Section 10
Design pattern: Open/Closed — add connectors without touching existing code.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from docforge.models import RawDocument


class IConnector(ABC):
    """Abstract base for all source connectors.

    Implement this to add a new content source (GitHub, SharePoint, Linear, etc.)
    See CONTRIBUTING.md for the step-by-step guide.
    """

    @abstractmethod
    async def fetch(self) -> list[RawDocument]:
        """Fetch documents from the remote source.

        Returns:
            List of RawDocument objects ready for the normalisation pipeline.

        Raises:
            ConnectorError: If the remote source is unreachable or auth fails.
        """
        ...

    @abstractmethod
    def validate_config(self) -> None:
        """Validate the connector configuration before fetching.

        Raises:
            ConnectorError: If required config (token, URL, etc.) is missing.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable connector name, e.g. 'GitHub'."""
        ...
