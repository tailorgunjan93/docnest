"""Tests for all document parsers.

Phase: 1  |  Run: pytest tests/test_parsers.py -v

Fixtures (put real files in tests/fixtures/ to run integration tests):
    tests/fixtures/sample.pdf   - a PDF with at least 2 headings and 1 table
    tests/fixtures/sample.docx  - a DOCX with headings, body text, and a table
    tests/fixtures/sample.xlsx  - see ExcelParser tests
"""

import pytest
from docnest.parsers.factory import ParserFactory
from docnest.parsers.pdf import DoclingPDFParser
from docnest.parsers.docx import DocxParser
from docnest.parsers.xlsx import ExcelParser
from docnest.parsers.html import HTMLParser
from docnest.parsers.md import MarkdownParser
from docnest.exceptions import UnsupportedFormatError


# ------------------------------------------------------------------ #
#  ParserFactory                                                       #
# ------------------------------------------------------------------ #

class TestParserFactory:
    def test_returns_pdf_parser_for_pdf(self):
        assert isinstance(ParserFactory().get("report.pdf"), DoclingPDFParser)

    def test_returns_docx_parser(self):
        assert isinstance(ParserFactory().get("doc.docx"), DocxParser)

    def test_returns_xlsx_parser(self):
        assert isinstance(ParserFactory().get("data.xlsx"), ExcelParser)

    def test_returns_html_parser(self):
        assert isinstance(ParserFactory().get("page.html"), HTMLParser)

    def test_returns_md_parser(self):
        assert isinstance(ParserFactory().get("README.md"), MarkdownParser)

    def test_raises_for_unsupported_format(self):
        with pytest.raises(UnsupportedFormatError):
            ParserFactory().get("archive.zip")

    def test_supports_returns_false_for_unknown(self):
        assert ParserFactory().supports("file.xyz") is False

    def test_supports_returns_true_for_pdf(self):
        assert ParserFactory().supports("report.pdf") is True

    def test_supports_returns_true_for_docx(self):
        assert ParserFactory().supports("brief.docx") is True

    def test_case_insensitive_extension_pdf(self):
        assert ParserFactory().supports("REPORT.PDF") is True

    def test_case_insensitive_extension_docx(self):
        assert ParserFactory().supports("DOC.DOCX") is True

    def test_register_adds_custom_parser(self):
        """register() inserts parser into registry (line 95)."""
        from docnest.parsers.base import IParser
        from docnest.models import RawDocument

        class CustomParser(IParser):
            def supports(self, f: str) -> bool:
                return f.endswith(".custom")
            def parse(self, f: str) -> RawDocument:
                raise NotImplementedError

        factory = ParserFactory()
        factory.register(CustomParser())
        assert factory.supports("file.custom")

    def test_register_at_non_zero_position(self):
        """register() with explicit position (line 95)."""
        from docnest.parsers.base import IParser
        from docnest.models import RawDocument

        class PriorityParser(IParser):
            def supports(self, f: str) -> bool:
                return f.endswith(".pri")
            def parse(self, f: str) -> RawDocument:
                raise NotImplementedError

        factory = ParserFactory()
        factory.register(PriorityParser(), position=len(factory._registry))
        assert factory.supports("file.pri")

    def test_unregister_removes_parser(self):
        """unregister() removes parser class (line 103)."""
        factory = ParserFactory()
        factory.unregister(DocxParser)
        assert not factory.supports("file.docx")

    def test_set_pdf_engine_pymupdf(self):
        """set_pdf_engine('pymupdf') swaps to PyMuPDF parser (lines 111-120)."""
        from docnest.parsers.pymupdf_pdf import PyMuPDFParser
        factory = ParserFactory()
        factory.set_pdf_engine("pymupdf")
        assert factory.supports("report.pdf")
        parser = factory.get("report.pdf")
        assert isinstance(parser, PyMuPDFParser)

    def test_set_pdf_engine_docling(self):
        """set_pdf_engine('docling') re-registers Docling parser (lines 111-120)."""
        factory = ParserFactory()
        factory.set_pdf_engine("pymupdf")  # switch to pymupdf first
        factory.set_pdf_engine("docling")  # switch back
        parser = factory.get("report.pdf")
        assert isinstance(parser, DoclingPDFParser)

    def test_factory_with_pymupdf_engine(self):
        """ParserFactory(pdf_engine='pymupdf') builds with PyMuPDF (lines 143-144)."""
        from docnest.parsers.pymupdf_pdf import PyMuPDFParser
        factory = ParserFactory(pdf_engine="pymupdf")
        assert isinstance(factory.get("report.pdf"), PyMuPDFParser)

    def test_registered_extensions_non_empty(self):
        assert ParserFactory()._registered_extensions() != "none"


# ------------------------------------------------------------------ #
#  DoclingPDFParser — unit tests (no fixture file required)           #
# ------------------------------------------------------------------ #

class TestDoclingPDFParserUnit:
    def test_supports_pdf(self):
        assert DoclingPDFParser().supports("report.pdf") is True

    def test_supports_case_insensitive(self):
        assert DoclingPDFParser().supports("REPORT.PDF") is True

    def test_does_not_support_docx(self):
        assert DoclingPDFParser().supports("doc.docx") is False

    def test_parse_missing_file_raises_parse_error(self):
        from docnest.exceptions import ParseError
        with pytest.raises(ParseError, match="not found"):
            DoclingPDFParser().parse("/tmp/does_not_exist_abc123.pdf")

    def test_lazy_converter_init(self):
        parser = DoclingPDFParser()
        assert parser._converter is None


# ------------------------------------------------------------------ #
#  DoclingPDFParser — integration (require tests/fixtures/sample.pdf) #
# ------------------------------------------------------------------ #

class TestDoclingPDFParserIntegration:
    def test_parse_returns_raw_document(self, sample_pdf):
        raw = DoclingPDFParser().parse(str(sample_pdf))
        assert raw.doc_id is not None
        assert raw.format == "pdf"
        assert raw.source.endswith(".pdf")

    def test_sections_are_extracted(self, sample_pdf):
        raw = DoclingPDFParser().parse(str(sample_pdf))
        assert len(raw.sections) > 0

    def test_section_ids_empty_from_parser(self, sample_pdf):
        """§ids must be empty strings — the Normaliser assigns them."""
        raw = DoclingPDFParser().parse(str(sample_pdf))
        for s in raw.sections:
            assert s.id == "", f"Parser must NOT assign §ids, got '{s.id}'"

    def test_tables_are_structured(self, sample_pdf):
        raw = DoclingPDFParser().parse(str(sample_pdf))
        tables = [t for s in raw.sections for t in s.tables]
        assert len(tables) > 0, "sample.pdf should contain at least one table"
        for t in tables:
            assert len(t.headers) > 0
            assert all(len(row) == len(t.headers) for row in t.rows)

    def test_section_titles_non_empty(self, sample_pdf):
        raw = DoclingPDFParser().parse(str(sample_pdf))
        for s in raw.sections:
            assert s.title.strip()

    def test_section_levels_valid(self, sample_pdf):
        raw = DoclingPDFParser().parse(str(sample_pdf))
        for s in raw.sections:
            assert 1 <= s.level <= 6


# ------------------------------------------------------------------ #
#  DocxParser — unit tests (no fixture file required)                 #
# ------------------------------------------------------------------ #

class TestDocxParserUnit:
    def test_supports_docx(self):
        assert DocxParser().supports("brief.docx") is True

    def test_supports_case_insensitive(self):
        assert DocxParser().supports("BRIEF.DOCX") is True

    def test_does_not_support_old_doc(self):
        # .doc (binary format) not supported by python-docx
        assert DocxParser().supports("old.doc") is False

    def test_does_not_support_pdf(self):
        assert DocxParser().supports("report.pdf") is False

    def test_parse_missing_file_raises_parse_error(self):
        from docnest.exceptions import ParseError
        with pytest.raises(ParseError, match="not found"):
            DocxParser().parse("/tmp/does_not_exist_abc123.docx")


# ------------------------------------------------------------------ #
#  DocxParser — integration (require tests/fixtures/sample.docx)      #
# ------------------------------------------------------------------ #

class TestDocxParserIntegration:
    def test_parse_returns_raw_document(self, sample_docx):
        raw = DocxParser().parse(str(sample_docx))
        assert raw.doc_id is not None
        assert raw.format == "docx"

    def test_sections_are_extracted(self, sample_docx):
        raw = DocxParser().parse(str(sample_docx))
        assert len(raw.sections) > 0

    def test_section_ids_empty_from_parser(self, sample_docx):
        raw = DocxParser().parse(str(sample_docx))
        for s in raw.sections:
            assert s.id == ""

    def test_heading_levels_detected(self, sample_docx):
        raw = DocxParser().parse(str(sample_docx))
        levels = {s.level for s in raw.sections}
        assert 1 in levels, "Expected at least one Heading 1 section"

    def test_tables_extracted(self, sample_docx):
        raw = DocxParser().parse(str(sample_docx))
        tables = [t for s in raw.sections for t in s.tables]
        assert len(tables) > 0

    def test_table_headers_and_rows_consistent(self, sample_docx):
        raw = DocxParser().parse(str(sample_docx))
        for s in raw.sections:
            for t in s.tables:
                assert len(t.headers) > 0
                assert all(len(row) == len(t.headers) for row in t.rows)

    def test_table_ids_unique(self, sample_docx):
        raw = DocxParser().parse(str(sample_docx))
        ids = [t.table_id for s in raw.sections for t in s.tables]
        assert len(ids) == len(set(ids))

    def test_body_text_present(self, sample_docx):
        raw = DocxParser().parse(str(sample_docx))
        assert any(s.text for s in raw.sections)


# ------------------------------------------------------------------ #
#  ExcelParser — integration (require tests/fixtures/sample.xlsx)     #
# ------------------------------------------------------------------ #

class TestExcelParser:
    def test_each_sheet_becomes_a_section(self, sample_xlsx):
        raw = ExcelParser().parse(str(sample_xlsx))
        assert len(raw.sections) >= 1

    def test_first_row_becomes_headers(self, sample_xlsx):
        raw = ExcelParser().parse(str(sample_xlsx))
        for s in raw.sections:
            for t in s.tables:
                assert len(t.headers) > 0
