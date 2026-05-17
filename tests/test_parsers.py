"""Tests for all document parsers.

Phase: 1  |  Run: pytest tests/test_parsers.py -v
"""
import pytest
from docforge.parsers.factory import ParserFactory
from docforge.parsers.pdf import DoclingPDFParser
from docforge.parsers.docx import DoclingDOCXParser
from docforge.parsers.xlsx import ExcelParser
from docforge.parsers.html import HTMLParser
from docforge.parsers.md import MarkdownParser
from docforge.exceptions import UnsupportedFormatError


class TestParserFactory:
    def test_returns_pdf_parser_for_pdf(self):
        factory = ParserFactory()
        parser = factory.get("report.pdf")
        assert isinstance(parser, DoclingPDFParser)

    def test_returns_docx_parser(self):
        assert isinstance(ParserFactory().get("doc.docx"), DoclingDOCXParser)

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


class TestDoclingPDFParser:
    """TODO (Phase 1): Uncomment and implement after DoclingPDFParser is done."""

    # def test_parse_returns_raw_document(self, sample_pdf):
    #     parser = DoclingPDFParser()
    #     raw = parser.parse(str(sample_pdf))
    #     assert raw.doc_id is not None
    #     assert len(raw.sections) > 0
    #     assert raw.format == "pdf"

    # def test_tables_are_structured_not_flat_text(self, sample_pdf):
    #     parser = DoclingPDFParser()
    #     raw = parser.parse(str(sample_pdf))
    #     sections_with_tables = [s for s in raw.sections if s.tables]
    #     assert len(sections_with_tables) > 0
    #     table = sections_with_tables[0].tables[0]
    #     assert len(table.headers) > 0
    #     assert all(len(row) == len(table.headers) for row in table.rows)

    pass


class TestExcelParser:
    """TODO (Phase 1): Uncomment and implement after ExcelParser is done."""

    # def test_each_sheet_becomes_a_section(self, sample_xlsx):
    #     parser = ExcelParser()
    #     raw = parser.parse(str(sample_xlsx))
    #     assert len(raw.sections) >= 2  # fixture has 2 sheets

    # def test_first_row_becomes_headers(self, sample_xlsx):
    #     parser = ExcelParser()
    #     raw = parser.parse(str(sample_xlsx))
    #     for section in raw.sections:
    #         for table in section.tables:
    #             assert len(table.headers) > 0

    pass
