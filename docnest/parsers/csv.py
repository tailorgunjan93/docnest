"""
CSV / TSV parser — pure stdlib, no extra dependencies.

Each file becomes one Section containing one TableData:
  - First non-empty row → column headers
  - Remaining rows     → data rows (row lengths normalised to header width)
  - Delimiter          → auto-detected (comma, tab, semicolon, pipe)
  - Encoding           → UTF-8 BOM-safe → UTF-8 → latin-1 cascade

TSV files (.tsv) always use tab as the delimiter regardless of sniffing.

Phase: 2  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from docnest.exceptions import ParseError
from docnest.models import RawDocument, Section, TableData
from docnest.parsers.base import IParser


class CSVParser(IParser):
    """Parses .csv and .tsv files into a RawDocument with a single TableData section.

    Strategy:
    - First non-empty row becomes column headers (always preserved).
    - Remaining non-empty rows become data rows in a TableData.
    - Row lengths are normalised to match the header width (pad / truncate).
    - Delimiter is auto-detected; TSV files always use tab.
    - Encoding cascade: utf-8-sig → utf-8 → latin-1.
    - Empty files and files with no valid headers raise ParseError.

    Usage::

        parser = CSVParser()
        raw = parser.parse("sales_data.csv")
        # raw.sections[0].tables[0].headers → column names
        # raw.sections[0].tables[0].rows    → all data rows
    """

    _SUPPORTED_SUFFIXES = (".csv", ".tsv")

    def supports(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self._SUPPORTED_SUFFIXES

    def parse(self, file_path: str) -> RawDocument:
        """Parse a CSV or TSV file into a RawDocument.

        Args:
            file_path: Path to the .csv or .tsv file.

        Returns:
            RawDocument with one Section and one TableData.

        Raises:
            ParseError: If the file is missing, empty, unreadable, or has no
                        valid column headers.
        """
        path = Path(file_path).resolve()

        # ── Validate file ────────────────────────────────────────────────
        if not path.exists():
            raise ParseError(f"CSV/TSV file not found: {path}")
        if path.stat().st_size == 0:
            raise ParseError(f"CSV/TSV file is empty: {path}")

        # ── Read text ────────────────────────────────────────────────────
        text = self._read_text(path)
        suffix = path.suffix.lower()

        # ── Detect delimiter ─────────────────────────────────────────────
        delimiter = self._detect_delimiter(text, suffix)

        # ── Parse rows ───────────────────────────────────────────────────
        reader = csv.reader(text.splitlines(), delimiter=delimiter)
        rows: list[list[str]] = [
            row for row in reader if any(cell.strip() for cell in row)
        ]

        if not rows:
            raise ParseError(f"CSV/TSV file contains no data rows: {path.name}")

        # First row → headers
        headers = [h.strip() for h in rows[0]]
        # Remove trailing empty header cells
        while headers and not headers[-1]:
            headers.pop()

        if not headers:
            raise ParseError(f"CSV/TSV file has no valid column headers: {path.name}")

        n_cols = len(headers)

        # Remaining rows → data
        data_rows: list[list[str]] = []
        for row in rows[1:]:
            if len(row) < n_cols:
                row = list(row) + [""] * (n_cols - len(row))
            elif len(row) > n_cols:
                row = row[:n_cols]
            data_rows.append(row)

        # ── Build structured objects ─────────────────────────────────────
        table = TableData(
            table_id="tbl_001",
            caption=None,
            headers=headers,
            rows=data_rows,
        )

        title = _filename_to_title(path.stem)
        section_text = self._table_text_summary(table, path.stem)
        section = Section(
            id="",          # assigned by Normaliser
            title=title,
            level=1,
            text=section_text,
            tables=[table],
            token_count=max(1, len(section_text.split())),
        )

        doc_id = self._make_doc_id(file_path)
        # Preserve actual format ("csv" or "tsv")
        fmt = suffix.lstrip(".")

        return RawDocument(
            doc_id=doc_id,
            title=title,
            source=str(path),
            format=fmt,
            sections=[section],
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _read_text(path: Path) -> str:
        """Read file content with encoding cascade: utf-8-sig → utf-8 → latin-1."""
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except (UnicodeDecodeError, LookupError):
                continue
        raise ParseError(
            f"Cannot decode '{path.name}' — not UTF-8 or latin-1. "
            f"Re-save the file as UTF-8 and try again."
        )

    @staticmethod
    def _detect_delimiter(text: str, suffix: str) -> str:
        """Return the field delimiter character for this file.

        TSV files always use tab.  For CSV files, Python's ``csv.Sniffer``
        is tried on the first 8 KB; if it fails or the file has only one
        column, comma is returned as the safe fallback.
        """
        if suffix == ".tsv":
            return "\t"

        sample = text[:8192]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
            return dialect.delimiter
        except csv.Error:
            return ","

    @staticmethod
    def _table_text_summary(table: TableData, stem: str) -> str:
        """Build a plain-text corpus entry for BM25 / embedding search."""
        parts: list[str] = [f"File: {stem}"]
        parts.append(f"Columns: {', '.join(table.headers)}")
        if table.rows:
            lines = [" | ".join(row) for row in table.rows]
            parts.append("Data:\n" + "\n".join(lines))
        return "\n".join(parts)


# ------------------------------------------------------------------ #
# Module-level utilities                                               #
# ------------------------------------------------------------------ #


def _filename_to_title(stem: str) -> str:
    """Convert a filename stem to a readable title.

    Examples::
        sales_data_2024 → Sales Data 2024
        employee-roster → Employee Roster
    """
    return re.sub(r"[-_]+", " ", stem).title()
