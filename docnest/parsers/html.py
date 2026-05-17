"""
HTML parser using BeautifulSoup.

Phase: 1  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
"""

from __future__ import annotations
from DOCNEST.parsers.base import IParser
from DOCNEST.models import RawDocument
from DOCNEST.exceptions import ParseError


class HTMLParser(IParser):
    """Parses HTML files using BeautifulSoup.

    TODO (Phase 1):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")
        Walk h1-h6 tags to build section hierarchy
        Extract <table> elements as TableData objects
    """

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith((".html", ".htm"))

    def parse(self, file_path: str) -> RawDocument:
        """Parse an HTML file into a RawDocument."""
        # TODO: Implement using BeautifulSoup
        raise NotImplementedError("HTMLParser not yet implemented.")
