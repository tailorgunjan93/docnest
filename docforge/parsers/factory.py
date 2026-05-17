"""
Parser factory — returns the correct IParser implementation for a given file.

Design pattern: Factory Method
Spec reference: docs/SPEC_DOCFORGE_PYPI.md — Section 9 (Design Patterns)

To register a new parser:
    1. Import it here
    2. Add it to the _PARSERS list
"""

from __future__ import annotations
from pathlib import Path

from docforge.parsers.base import IParser
from docforge.parsers.pdf import DoclingPDFParser
from docforge.parsers.docx import DoclingDOCXParser
from docforge.parsers.xlsx import ExcelParser
from docforge.parsers.html import HTMLParser
from docforge.parsers.md import MarkdownParser
from docforge.exceptions import UnsupportedFormatError

# Registry — order matters: first matching parser wins
_PARSERS: list[IParser] = [
    DoclingPDFParser(),
    DoclingDOCXParser(),
    ExcelParser(),
    HTMLParser(),
    MarkdownParser(),
]


class ParserFactory:
    """Selects and returns the correct parser for a given file path.

    Usage:
        factory = ParserFactory()
        parser = factory.get("report.pdf")
        raw_doc = parser.parse("report.pdf")
    """

    def get(self, file_path: str) -> IParser:
        """Return the first parser that supports the given file.

        Args:
            file_path: Path to the document file.

        Returns:
            An IParser implementation ready to parse the file.

        Raises:
            UnsupportedFormatError: If no registered parser supports the format.
        """
        for parser in _PARSERS:
            if parser.supports(file_path):
                return parser
        suffix = Path(file_path).suffix
        raise UnsupportedFormatError(
            f"No parser found for '{suffix}'. "
            f"Supported: pdf, docx, pptx, xlsx, html, md. "
            f"See CONTRIBUTING.md to add a new parser."
        )

    def supports(self, file_path: str | Path) -> bool:
        """Return True if any registered parser supports this file."""
        return any(p.supports(str(file_path)) for p in _PARSERS)
