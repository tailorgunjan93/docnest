"""
Parser factory — returns the correct IParser for a given file.

Design pattern: Factory Method + Registry
Spec reference: docs/SPEC_DOCNEST_PYPI.md — Section 9 (Design Patterns)

Built-in parsers are registered at import time.  Third-party parsers can be
added at runtime with ``ParserFactory.register()`` — no source edits needed.

PDF engine is selectable:
    factory = ParserFactory(pdf_engine="pymupdf")   # fast, font-size headings
    factory = ParserFactory(pdf_engine="docling")   # ML layout analysis (default)
"""

from __future__ import annotations
from pathlib import Path

from docnest.parsers.base import IParser
from docnest.exceptions import UnsupportedFormatError


class ParserFactory:
    """Selects and returns the correct parser for a given file path.

    The registry is instance-level so different pipeline instances can use
    different parser sets without global state pollution.

    Usage::

        # Default — Docling PDF parser
        factory = ParserFactory()
        raw_doc = factory.get("report.pdf").parse("report.pdf")

        # Fast PDF with PyMuPDF
        factory = ParserFactory(pdf_engine="pymupdf")

        # Register a custom parser at runtime
        factory.register(MyXMLParser())
    """

    def __init__(self, pdf_engine: str = "docling") -> None:
        """
        Args:
            pdf_engine: Which PDF parser to register by default.
                        ``"docling"`` (default) — ML layout analysis, OCR support.
                        ``"pymupdf"`` — fast font-size heuristic, no ML downloads.
        """
        # Ordered registry — first match wins
        self._registry: list[IParser] = []
        self._build_default_registry(pdf_engine)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def get(self, file_path: str) -> IParser:
        """Return the first registered parser that supports this file.

        Args:
            file_path: Path to the document file.

        Returns:
            An IParser ready to call ``.parse()``.

        Raises:
            UnsupportedFormatError: If no registered parser handles the format.
        """
        for parser in self._registry:
            if parser.supports(file_path):
                return parser
        suffix = Path(file_path).suffix.lower() or "(no extension)"
        raise UnsupportedFormatError(
            f"No parser registered for '{suffix}'. "
            f"Registered formats: {self._registered_extensions()}. "
            f"Call factory.register(MyParser()) to add a new format."
        )

    def supports(self, file_path: str | Path) -> bool:
        """Return True if any registered parser supports this file."""
        return any(p.supports(str(file_path)) for p in self._registry)

    def register(self, parser: IParser, position: int = 0) -> None:
        """Register a new parser.

        Args:
            parser:   An IParser implementation to add.
            position: Insert position in the registry (default 0 = highest priority).
                      Use ``len(factory._registry)`` to append at lowest priority.

        Example::

            factory = ParserFactory()
            factory.register(MyPDFParser(), position=0)  # takes priority over built-ins
        """
        self._registry.insert(position, parser)

    def unregister(self, parser_class: type) -> None:
        """Remove all parsers of the given class from the registry.

        Args:
            parser_class: The IParser subclass to remove, e.g. ``DoclingPDFParser``.
        """
        self._registry = [p for p in self._registry if not isinstance(p, parser_class)]

    def set_pdf_engine(self, engine: str) -> None:
        """Hot-swap the PDF parser engine on an existing factory instance.

        Args:
            engine: ``"docling"`` or ``"pymupdf"``.
        """
        from docnest.parsers.pdf import DoclingPDFParser
        from docnest.parsers.pymupdf_pdf import PyMuPDFParser

        self.unregister(DoclingPDFParser)
        self.unregister(PyMuPDFParser)

        if engine == "pymupdf":
            self._registry.insert(0, PyMuPDFParser())
        else:
            self._registry.insert(0, DoclingPDFParser())

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _build_default_registry(self, pdf_engine: str) -> None:
        """Populate the default parser registry."""
        from docnest.parsers.csv import CSVParser
        from docnest.parsers.docx import DocxParser
        from docnest.parsers.xlsx import ExcelParser
        from docnest.parsers.html import HTMLParser
        from docnest.parsers.md import MarkdownParser

        # Non-PDF parsers (always the same)
        self._registry = [
            DocxParser(),
            ExcelParser(),
            CSVParser(),
            HTMLParser(),
            MarkdownParser(),
        ]

        # PDF parser — chosen by engine param
        if pdf_engine == "pymupdf":
            from docnest.parsers.pymupdf_pdf import PyMuPDFParser
            self._registry.insert(0, PyMuPDFParser())
        else:
            from docnest.parsers.pdf import DoclingPDFParser
            self._registry.insert(0, DoclingPDFParser())

    def _registered_extensions(self) -> str:
        """Build a readable list of supported extensions for error messages."""
        exts: list[str] = []
        for p in self._registry:
            name = type(p).__name__.replace("Parser", "").lower()
            exts.append(name)
        return ", ".join(exts) if exts else "none"
