"""
Excel parser using openpyxl.

Each worksheet becomes one Section. Every table is a TableData object with
headers and rows — column context is NEVER lost.

Improvements over initial implementation:
- Handles row-length mismatches (pads short rows, truncates long rows)
- Detects multiple logical tables within a single sheet (separated by empty rows)
- Generates richer section text from cell content for better RAG retrieval
- Uses consistent table IDs (tbl_001, tbl_002, …)
- Raises clear error for .xls files (openpyxl only supports .xlsx)
- Properly builds Section with tables via constructor, not attribute reassignment

Phase: 1 | Issue: github.com/tailorgunjan93/docnest/issues/4
Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
"""

from __future__ import annotations

import re
from pathlib import Path

from docnest.exceptions import ParseError
from docnest.models import RawDocument, Section, TableData
from docnest.parsers.base import IParser

# Minimum number of non-empty data rows (excluding headers) for a group
# of rows to be considered a table.
_MIN_TABLE_DATA_ROWS = 0


class ExcelParser(IParser):
    """Parses .xlsx Excel files using openpyxl.

    Strategy:
    - Each worksheet → one Section (title = sheet name)
    - Multiple logical tables per sheet are detected: an empty row signals
      the start of a new table (new header row + data rows).
    - First row of each logical table = column headers (always preserved)
    - Remaining rows = data rows in a TableData
    - Row lengths are normalised to match the header count
    - Empty sheets are skipped

    Usage::

        parser = ExcelParser()
        raw = parser.parse("sales_data.xlsx")
        # raw.sections[i].title → sheet name
        # raw.sections[i].tables → list of TableData with headers+rows
    """

    # Suffixes this parser handles.  NOTE: .xls (binary BIFF format) is
    # NOT supported by openpyxl — we list it in supports() so the factory
    # routes it here, then raise a clear error in parse().
    _SUPPORTED_SUFFIXES = (".xlsx", ".xls")

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith(self._SUPPORTED_SUFFIXES)

    def parse(self, file_path: str) -> RawDocument:
        """Parse an Excel file into a RawDocument with structured tables.

        Args:
            file_path: Path to the .xlsx file.

        Returns:
            RawDocument where each sheet is a Section containing one or
            more TableData objects (one per logical table in the sheet).

        Raises:
            ParseError: If the file is missing, empty, .xls (unsupported),
                or openpyxl fails.
        """
        path = Path(file_path).resolve()

        # ── Validate file ────────────────────────────────────────────────
        if not path.exists():
            raise ParseError(f"Excel file not found: {path}")
        if path.stat().st_size == 0:
            raise ParseError(f"Excel file is empty: {path}")

        # openpyxl cannot read .xls (legacy BIFF format); give a clear message
        if path.suffix.lower() == ".xls":
            raise ParseError(
                f".xls (BIFF) format is not supported — only .xlsx. "
                f"Convert '{path.name}' to .xlsx first "
                f"(e.g. using LibreOffice: libreoffice --convert-to xlsx '{path.name}')"
            )

        # ── Import openpyxl ──────────────────────────────────────────────
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

        # ── Parse sheets ─────────────────────────────────────────────────
        sections: list[Section] = []
        global_table_counter = 0

        for sheet in wb.worksheets:
            # Collect non-empty rows
            rows_raw: list[list[str]] = []
            for row in sheet.iter_rows(values_only=True):
                row_vals = [str(c) if c is not None else "" for c in row]
                if any(v.strip() for v in row_vals):
                    rows_raw.append(row_vals)

            if not rows_raw:
                continue  # skip empty sheets

            # Split rows into logical tables (separated by all-empty "gap" rows
            # that have already been filtered out — we detect table boundaries
            # by finding header-like rows after a gap).
            tables_in_sheet = self._split_into_tables(rows_raw)
            section_text_parts: list[str] = []

            section_tables: list[TableData] = []
            for header_row, data_rows in tables_in_sheet:
                global_table_counter += 1
                table = self._build_table(
                    header_row, data_rows, table_id=f"tbl_{global_table_counter:03d}"
                )
                if table is not None:
                    section_tables.append(table)
                    # Add a text summary of the table for RAG retrieval
                    section_text_parts.append(
                        self._table_text_summary(table, sheet.title)
                    )

            if not section_tables:
                continue  # sheet had rows but no valid tables

            section_text = "\n".join(section_text_parts)
            section = Section(
                id="",
                title=sheet.title,
                level=1,
                text=section_text,
                tables=section_tables,
            )
            sections.append(section)

        wb.close()

        if not sections:
            raise ParseError(
                f"Excel file contains no data sheets: {path.name}"
            )

        doc_id = self._make_doc_id(file_path)
        title = _filename_to_title(path.stem)

        return RawDocument(
            doc_id=doc_id,
            title=title,
            source=str(path),
            format="xlsx",
            sections=sections,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _split_into_tables(
        self, rows: list[list[str]]
    ) -> list[tuple[list[str], list[list[str]]]]:
        """Split a sheet's rows into logical tables.

        A new logical table starts when a row that looks like a header
        (all cells are short, non-numeric labels) is encountered **after
        at least one data row that is predominantly numeric**. This
        prevents false splits where a data row with text values (e.g.
        "Alice", "30", "NYC") is mistaken for a header.

        The heuristic is:
        - The first row is always the first table's header.
        - A subsequent row triggers a new table ONLY if:
          1. It looks like a header (short, mostly text labels), AND
          2. The previous row was predominantly numeric (suggesting it
             was the last data row of the previous table).

        Returns:
            List of (header_row, data_rows) tuples.
        """
        if not rows:
            return []

        result: list[tuple[list[str], list[list[str]]]] = []
        current_header: list[str] | None = None
        current_data: list[list[str]] = []
        prev_row_was_data: bool = False

        for i, row in enumerate(rows):
            if current_header is None:
                # First row is always the header of the first table
                current_header = row
            elif (
                self._looks_like_header(row)
                and prev_row_was_data
                and current_data
            ):
                # This row looks like a new header after numeric data →
                # start a new table
                result.append((current_header, current_data))
                current_header = row
                current_data = []
                prev_row_was_data = False
            else:
                current_data.append(row)
                prev_row_was_data = self._is_mostly_numeric(row)

        # Don't forget the last table
        if current_header is not None:
            result.append((current_header, current_data))

        return result

    @staticmethod
    def _looks_like_header(row: list[str]) -> bool:
        """Heuristic: does this row look like a table header?

        A header row typically has:
        - Multiple non-empty cells
        - Cells are short text labels (not long paragraphs or pure numbers)
        - At least 2 non-empty cells
        """
        non_empty = [c.strip() for c in row if c.strip()]
        if len(non_empty) < 2:
            return False

        # Header cells tend to be short text labels, not numbers
        text_cells = [c for c in non_empty if not _is_numeric(c)]
        if len(text_cells) < len(non_empty) * 0.5:
            return False  # majority are numbers → probably a data row

        # Header cells tend to be short
        avg_len = sum(len(c) for c in non_empty) / len(non_empty)
        return avg_len <= 50

    @staticmethod
    def _is_mostly_numeric(row: list[str]) -> bool:
        """Return True if the majority of non-empty cells are numeric.

        Used to detect the boundary between tables: a data row with
        mostly numbers followed by a label row signals a new table.
        """
        non_empty = [c.strip() for c in row if c.strip()]
        if not non_empty:
            return False
        numeric_count = sum(1 for c in non_empty if _is_numeric(c))
        return numeric_count >= len(non_empty) * 0.5

    @staticmethod
    def _build_table(
        header_row: list[str],
        data_rows: list[list[str]],
        table_id: str,
    ) -> TableData | None:
        """Build a TableData from header and data rows, normalising lengths.

        Pads short rows and truncates long rows so every row has exactly
        len(headers) columns, satisfying the TableData contract.
        """
        headers = [h.strip() for h in header_row]
        if not headers or not any(headers):
            return None

        # Remove trailing empty headers
        while headers and not headers[-1].strip():
            headers.pop()

        if not headers:
            return None

        n_cols = len(headers)
        normalised_rows: list[list[str]] = []
        for row in data_rows:
            # Pad short rows with empty strings, truncate long rows
            if len(row) < n_cols:
                row = list(row) + [""] * (n_cols - len(row))
            elif len(row) > n_cols:
                row = row[:n_cols]
            normalised_rows.append(row)

        return TableData(
            table_id=table_id,
            caption=None,
            headers=headers,
            rows=normalised_rows,
        )

    @staticmethod
    def _table_text_summary(table: TableData, sheet_name: str) -> str:
        """Generate a text summary of a table for RAG retrieval.

        Includes column headers and a compact representation of the data
        so that embedding/search can find relevant content without needing
        to inspect the structured table data directly.
        """
        parts: list[str] = [f"Sheet: {sheet_name}"]
        if table.caption:
            parts.append(f"Table: {table.caption}")
        parts.append(f"Columns: {', '.join(table.headers)}")

        # Include a compact preview of up to 5 data rows
        preview_rows = table.rows[:5]
        if preview_rows:
            lines: list[str] = []
            for row in preview_rows:
                line = " | ".join(row)
                lines.append(line)
            parts.append("Data preview:\n" + "\n".join(lines))
            if len(table.rows) > 5:
                parts.append(f"... and {len(table.rows) - 5} more rows")

        return "\n".join(parts)


# ------------------------------------------------------------------ #
# Module-level utilities                                               #
# ------------------------------------------------------------------ #


def _filename_to_title(stem: str) -> str:
    """Convert a filename stem to a readable title.

    Examples::
        project_brief_v2 → Project Brief V2
        meeting-notes → Meeting Notes
    """
    return re.sub(r"[-_]+", " ", stem).title()


def _is_numeric(s: str) -> bool:
    """Return True if the string represents a number (int, float, or with commas)."""
    s = s.strip().replace(",", "")
    try:
        float(s)
        return True
    except ValueError:
        return False
