"""
Word document parser using Docling.

Phase: 1  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
"""

from __future__ import annotations
from DOCNEST.parsers.base import IParser
from DOCNEST.models import RawDocument
from DOCNEST.exceptions import ParseError


class DoclingDOCXParser(IParser):
    """Parses .docx Word documents using Docling.

    TODO (Phase 1):
        Same approach as DoclingPDFParser — Docling handles DOCX natively.
        from docling.document_converter import DocumentConverter
    """

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith((".docx", ".doc"))

    def parse(self, file_path: str) -> RawDocument:
        """Parse a Word document into a RawDocument."""
        # TODO: Implement using Docling
        raise NotImplementedError("DoclingDOCXParser not yet implemented.")
