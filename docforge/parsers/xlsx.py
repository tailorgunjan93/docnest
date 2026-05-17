"""
Excel parser using openpyxl.

Each worksheet becomes one Section. Every table is a TableData object with
headers and rows — column context is NEVER lost.

Phase: 1  |  Issue: github.com/tailorgunjan93/docforged/issues/4
Spec: docs/SPEC_DOCFORGE_PYPI.md — Section 10
"""

from __future__ import annotations
from docforge.parsers.base import IParser
from docforge.models import RawDocument
from docforge.exceptions import ParseError


class ExcelParser(IParser):
    """Parses .xlsx Excel files using openpyxl.

    Strategy:
    - Each worksheet → one Section (title = sheet name)
    - Each contiguous block of data → one TableData
    - First row of each table = headers (always preserved)
    - Empty rows = table separator

    TODO (Phase 1):
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        for sheet in wb.worksheets:
            extract headers from row 1
            build rows from remaining rows
            create TableData(caption=sheet.title, headers=..., rows=...)
            create Section(title=sheet.title, tables=[table])
    """

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith((".xlsx", ".xls"))

    def parse(self, file_path: str) -> RawDocument:
        """Parse an Excel file into a RawDocument with structured tables."""
        # TODO: Implement using openpyxl
        raise NotImplementedError("ExcelParser not yet implemented. See issue #4.")
