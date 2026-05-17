"""
PDF parser using Docling.

Handles text-based PDFs (headings, paragraphs, tables) and scanned PDFs
(OCR via Docling's built-in Tesseract integration).

Tables are extracted as structured TableData objects — never as flat strings.
Images are captured as ImageRef entries with asset paths.

Phase: 1  |  Spec: docs/SPEC_DOCNEST_PYPI.md — Section 10
Docling docs: https://ds4sd.github.io/docling/
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from docnest.parsers.base import IParser
from docnest.models import RawDocument, Section, TableData, ImageRef
from docnest.exceptions import ParseError


# Docling label strings for each content type
_HEADING_LABELS = {"section_header", "title"}
_TEXT_LABELS = {"text", "paragraph", "list_item", "caption", "footnote"}
_TABLE_LABEL = "table"
_PICTURE_LABEL = "picture"
_IGNORE_LABELS = {"page_header", "page_footer", "page_number"}


class DoclingPDFParser(IParser):
    """Parses PDF files using Docling (text-based and scanned via OCR).

    Docling handles layout analysis, table detection, and heading hierarchy
    automatically. This parser maps Docling output to DocNest's RawDocument
    model, section-by-section.

    Usage:
        parser = DoclingPDFParser()
        raw = parser.parse("/path/to/report.pdf")
        # raw.sections        → list of Section objects
        # raw.sections[n].tables → list of TableData objects
    """

    def __init__(self) -> None:
        # Lazy-loaded — Docling model init is expensive (~3-5 s first call)
        self._converter: object | None = None

    # ------------------------------------------------------------------ #
    #  IParser interface                                                   #
    # ------------------------------------------------------------------ #

    def supports(self, file_path: str) -> bool:
        """Return True for .pdf files."""
        return file_path.lower().endswith(".pdf")

    def parse(self, file_path: str) -> RawDocument:
        """Parse a PDF into a RawDocument.

        Args:
            file_path: Absolute or relative path to the PDF file.

        Returns:
            RawDocument with sections, tables, and images extracted.
            Section ids (§N) are NOT assigned here — the Normaliser does that.

        Raises:
            ParseError: File missing, empty, or Docling conversion failed.
        """
        path = Path(file_path).resolve()
        if not path.exists():
            raise ParseError(f"PDF not found: {path}")
        if path.stat().st_size == 0:
            raise ParseError(f"PDF is empty: {path}")

        try:
            result = self._get_converter().convert(str(path))  # type: ignore[union-attr]
        except Exception as exc:
            raise ParseError(
                f"Docling failed to convert '{path.name}': {exc}"
            ) from exc

        doc = result.document
        title = self._extract_title(doc, path)
        sections = self._build_sections(doc)

        return RawDocument(
            doc_id=self._make_doc_id(file_path),
            title=title,
            source=str(path),
            format="pdf",
            sections=sections,
        )

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _get_converter(self) -> object:
        """Lazy-init the Docling DocumentConverter (loads ML models on first call)."""
        if self._converter is None:
            try:
                from docling.document_converter import DocumentConverter  # type: ignore[import]
            except ImportError as exc:
                raise ParseError(
                    "Docling is not installed. Run: pip install docling"
                ) from exc
            self._converter = DocumentConverter()
        return self._converter

    def _extract_title(self, doc: object, path: Path) -> str:
        """Return document title from Docling metadata, or derive from filename."""
        for item, _ in doc.iterate_items():  # type: ignore[attr-defined]
            if str(item.label).lower() == "title":
                text = getattr(item, "text", "").strip()
                if text:
                    return text
        return _filename_to_title(path.stem)

    def _build_sections(self, doc: object) -> list[Section]:
        """Walk Docling items and group content into Section objects.

        Rules:
        - section_header / title  → starts a new Section
        - text / list_item / etc. → appended to the current Section's text
        - table                   → TableData added to current Section
        - picture                 → ImageRef added to current Section
        - page_header/footer      → ignored
        - Content before first heading → implicit 'Introduction' Section (level 1)
        """
        sections: list[Section] = []
        current: Optional[Section] = None
        table_counter = 0
        image_counter = 0

        for item, depth in doc.iterate_items():  # type: ignore[attr-defined]
            label = str(item.label).lower()

            if label in _IGNORE_LABELS:
                continue

            if label in _HEADING_LABELS:
                if current is not None:
                    current.text = current.text.strip()
                    sections.append(current)
                heading_text = getattr(item, "text", "").strip() or "Section"
                # Docling's depth = nesting level in doc tree; clamp to 1-6
                h_level = max(1, min(6, depth if depth and depth > 0 else 1))
                current = Section(
                    id="",          # Normaliser assigns §ids
                    title=heading_text,
                    level=h_level,
                    text="",
                )

            elif label in _TEXT_LABELS:
                text = getattr(item, "text", "").strip()
                if not text:
                    continue
                if current is None:
                    current = Section(id="", title="Introduction", level=1, text="")
                current.text += text + "\n\n"

            elif label == _TABLE_LABEL:
                table_counter += 1
                table_data = self._extract_table(item, table_counter)
                if table_data:
                    if current is None:
                        current = Section(id="", title="Tables", level=1, text="")
                    current.tables.append(table_data)

            elif label == _PICTURE_LABEL:
                image_counter += 1
                image_ref = self._extract_image_ref(item, image_counter)
                if image_ref:
                    if current is None:
                        current = Section(id="", title="Figures", level=1, text="")
                    current.images.append(image_ref)

        if current is not None:
            current.text = current.text.strip()
            sections.append(current)

        return sections

    def _extract_table(self, item: object, counter: int) -> Optional[TableData]:
        """Convert a Docling TableItem to a TableData model.

        Tries DataFrame export first (cleanest), then falls back to raw cell
        iteration so we don't depend on pandas being installed.
        """
        table_id = f"tbl_{counter:03d}"

        # Attempt 1: pandas DataFrame export
        try:
            df = item.export_to_dataframe()  # type: ignore[attr-defined]
            headers = [str(c) for c in df.columns.tolist()]
            rows = [[str(v) for v in row] for row in df.values.tolist()]
            if headers:
                return TableData(table_id=table_id, headers=headers, rows=rows)
        except Exception:
            pass

        # Attempt 2: raw cell iteration via item.data.table_cells
        try:
            cells = item.data.table_cells  # type: ignore[attr-defined]
            if not cells:
                return None
            num_cols = max(c.start_col_offset_idx + 1 for c in cells)
            num_rows = max(c.start_row_offset_idx + 1 for c in cells)
            grid: list[list[str]] = [[""] * num_cols for _ in range(num_rows)]
            for cell in cells:
                grid[cell.start_row_offset_idx][cell.start_col_offset_idx] = (
                    cell.text.strip()
                )
            headers = grid[0]
            rows = grid[1:]
            return TableData(table_id=table_id, headers=headers, rows=rows)
        except Exception:
            return None

    def _extract_image_ref(self, item: object, counter: int) -> Optional[ImageRef]:
        """Build an ImageRef from a Docling PictureItem."""
        try:
            caption = ""
            captions = getattr(item, "captions", [])  # type: ignore[attr-defined]
            if captions:
                caption = " ".join(
                    getattr(c, "text", "") for c in captions
                ).strip()
            return ImageRef(
                image_id=f"img_{counter:03d}",
                alt=caption or None,
                asset_path=f"assets/img_{counter:03d}.png",
            )
        except Exception:
            return None


# ------------------------------------------------------------------ #
#  Utility                                                             #
# ------------------------------------------------------------------ #

def _filename_to_title(stem: str) -> str:
    """Convert a filename stem to a readable title.

    Examples:
        annual_report_2024  → Annual Report 2024
        Q3-earnings-summary → Q3 Earnings Summary
    """
    return re.sub(r"[-_]+", " ", stem).title()
