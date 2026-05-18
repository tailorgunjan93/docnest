"""
Excel parser using openpyxl.

Each worksheet becomes one Section. Every table is a TableData object with
headers and rows — column context is NEVER lost.

Phase: 1  |  Issue: github.com/tailorgunjan93/DOCNESTd/issues/4
Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
"""

from __future__ import annotations

from pathlib import Path
from docnest.parsers.base import IParser
from docnest.models import RawDocument, Section, TableData
from docnest.exceptions import ParseError


class ExcelParser(IParser):
    """Parses .xlsx Excel files using openpyxl.

    Strategy:
    - Each worksheet → one Section (title = sheet name)
    - First row of each sheet = column headers (always preserved)
    - Remaining rows = data rows in a TableData
    - Empty sheets are skipped

    Usage:
        parser = ExcelParser()
        raw = parser.parse("sales_data.xlsx")
        # raw.sections[i].title  → sheet name
        # raw.sections[i].tables → list of TableData with headers+rows
    """

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith((".xlsx", ".xls"))

    def parse(self, file_path: str) -> RawDocument:
        """Parse an Excel file into a RawDocument with structured tables.

        Args:
            file_path: Path to the .xlsx or .xls file.

        Returns:
            RawDocument where each sheet is a Section containing a TableData.

        Raises:
            ParseError: If the file is missing, empty, or openpyxl fails.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise ParseError(f"Excel file not found: {path}")
        if path.stat().st_size == 0:
            raise ParseError(f"Excel file is empty: {path}")

        try:
            import openpyxl  # type: ignore[import]
        except ImportError as exc:
            raise ParseError(
                "openpyxl is not installed. Run: pip install openpyxl"
            ) from exc

        try:
            wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        except Exception as exc:
            raise ParseError(
                f"openpyxl failed to open '{path.name}': {exc}"
            ) from exc

        sections: list[Section] = []

        for sheet in wb.worksheets:
            rows_raw: list[list[str]] = []
            for row in sheet.iter_rows(values_only=True):
                # Skip entirely-None rows (empty rows)
                row_vals = [str(c) if c is not None else "" for c in row]
                if any(v.strip() for v in row_vals):
                    rows_raw.append(row_vals)

            if not rows_raw:
                continue  # skip empty sheets

            headers = rows_raw[0]
            data_rows = rows_raw[1:]

            table = TableData(
                table_id=f"sheet_{sheet.title}",
                caption=sheet.title,
                headers=headers,
                rows=data_rows,
            )
            section = Section(
                id="",
                title=sheet.title,
                level=1,
                text=f"Spreadsheet sheet: {sheet.title}",
            )
            section.tables = [table]
            sections.append(section)

        wb.close()

        doc_id = self._make_doc_id(file_path)
        title = path.stem.replace("_", " ").replace("-", " ").title()

        return RawDocument(
            doc_id=doc_id,
            title=title,
            source=str(path),
            format="xlsx",
            sections=sections,
        )
