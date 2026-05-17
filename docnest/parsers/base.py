"""
Abstract base class for all DOCNEST document parsers.

Every parser converts a raw file into a RawDocument. Parsers are responsible
for Stage 1 (structure extraction) and part of Stage 2 (table preservation).
They do NOT assign §ids — that is the Normaliser's job.

Spec reference: docs/SPEC_DOCNEST_PYPI.md — Section 10 (Interfaces & Classes)
Design pattern: Template Method (parse() defines the skeleton, _extract() is overridden)
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path

from DOCNEST.models import RawDocument


class IParser(ABC):
    """Abstract base class for all document parsers.

    Implement this to add support for a new document format.
    Register your implementation in parsers/factory.py.
    """

    @abstractmethod
    def parse(self, file_path: str) -> RawDocument:
        """Parse the file and return a structured RawDocument.

        Args:
            file_path: Absolute path to the source file.

        Returns:
            RawDocument with sections, tables, and heading hierarchy extracted.
            Section ids (§N) are NOT assigned here — that is the Normaliser's job.

        Raises:
            ParseError: If the file cannot be read or parsed.
        """
        ...

    @abstractmethod
    def supports(self, file_path: str) -> bool:
        """Return True if this parser handles the given file.

        Args:
            file_path: Path to check (uses file extension by default).

        Returns:
            True if this parser can handle the file format.
        """
        ...

    def _make_doc_id(self, file_path: str) -> str:
        """Generate a stable doc_id from the file path."""
        return Path(file_path).stem.lower().replace(" ", "-")
