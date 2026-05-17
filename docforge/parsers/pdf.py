"""
PDF parser using Docling.

Handles both text-based and scanned PDFs (via Docling's built-in OCR).
Tables are extracted as structured { caption, headers, rows[] } — never as flat text.

Phase: 1 (Core Parser & Normaliser)
Issue: github.com/tailorgunjan93/docforged/issues/1
Spec: docs/SPEC_DOCFORGE_PYPI.md — Section 10
"""

from __future__ import annotations
from docforge.parsers.base import IParser
from docforge.models import RawDocument
from docforge.exceptions import ParseError


class DoclingPDFParser(IParser):
    """Parses PDF files (text-based and scanned) using Docling.

    Docling handles:
    - Text-based PDFs: heading detection, paragraph extraction, table recognition
    - Scanned PDFs: OCR via Tesseract (bundled with Docling)

    TODO (Phase 1):
        1. pip install docling
        2. from docling.document_converter import DocumentConverter
        3. converter = DocumentConverter()
        4. result = converter.convert(file_path)
        5. Map result.document to RawDocument + Section list
        6. For each table in result: map to TableData(caption, headers, rows)
        7. See Docling docs: https://ds4sd.github.io/docling/
    """

    def supports(self, file_path: str) -> bool:
        return file_path.lower().endswith(".pdf")

    def parse(self, file_path: str) -> RawDocument:
        """Parse a PDF file and return a structured RawDocument.

        Args:
            file_path: Absolute path to the PDF file.

        Returns:
            RawDocument with sections and tables extracted.
            Tables are TableData objects — not flat strings.

        Raises:
            ParseError: If the PDF cannot be read or Docling fails.
        """
        # TODO: Implement using Docling
        # from docling.document_converter import DocumentConverter
        # converter = DocumentConverter()
        # result = converter.convert(file_path)
        # return self._map_to_raw_document(result, file_path)
        raise NotImplementedError(
            "DoclingPDFParser not yet implemented. "
            "See issue #1: github.com/tailorgunjan93/docforged/issues/1"
        )
