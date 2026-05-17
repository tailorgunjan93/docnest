"""
Markdown parser using python-markdown.

Phase: 1  |  Spec: docs/SPEC_DOCFORGE_PYPI.md — Section 10
"""

from __future__ import annotations
from docforge.parsers.base import IParser
from docforge.models import RawDocument
from docforge.exceptions import ParseError


class MarkdownParser(IParser):
    """Parses Markdown files into structured sections.

    TODO (Phase 1):
        import markdown
        from markdown.treeprocessors import Treeprocessor
        Walk heading elements (h1-h6) to build section hierarchy
        Preserve fenced code blocks and lists within sections
    """

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith((".md", ".markdown"))

    def parse(self, file_path: str) -> RawDocument:
        """Parse a Markdown file into a RawDocument."""
        # TODO: Implement using python-markdown
        raise NotImplementedError("MarkdownParser not yet implemented.")
