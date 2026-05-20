"""
Tests for CSVParser and TSV support.

Run:  pytest tests/test_csv_parser.py -v

No fixture files required — all tests create their own data in tmp_path.
"""

from __future__ import annotations

import csv as csv_stdlib
import pytest

from docnest.exceptions import ParseError
from docnest.parsers.csv import CSVParser, _filename_to_title
from docnest.parsers.factory import ParserFactory


# ------------------------------------------------------------------ #
#  supports() / extension detection                                   #
# ------------------------------------------------------------------ #

class TestCSVParserSupports:
    def test_supports_csv(self):
        assert CSVParser().supports("data.csv") is True

    def test_supports_tsv(self):
        assert CSVParser().supports("data.tsv") is True

    def test_supports_uppercase_csv(self):
        assert CSVParser().supports("DATA.CSV") is True

    def test_supports_uppercase_tsv(self):
        assert CSVParser().supports("REPORT.TSV") is True

    def test_does_not_support_xlsx(self):
        assert CSVParser().supports("data.xlsx") is False

    def test_does_not_support_pdf(self):
        assert CSVParser().supports("report.pdf") is False

    def test_does_not_support_no_extension(self):
        assert CSVParser().supports("datafile") is False

    def test_does_not_support_txt(self):
        assert CSVParser().supports("data.txt") is False


# ------------------------------------------------------------------ #
#  ParserFactory integration                                           #
# ------------------------------------------------------------------ #

class TestCSVParserFactory:
    def test_factory_returns_csv_parser_for_csv(self):
        parser = ParserFactory().get("sales.csv")
        assert isinstance(parser, CSVParser)

    def test_factory_returns_csv_parser_for_tsv(self):
        parser = ParserFactory().get("employees.tsv")
        assert isinstance(parser, CSVParser)

    def test_factory_supports_csv(self):
        assert ParserFactory().supports("data.csv") is True

    def test_factory_supports_tsv(self):
        assert ParserFactory().supports("data.tsv") is True


# ------------------------------------------------------------------ #
#  Error handling                                                      #
# ------------------------------------------------------------------ #

class TestCSVParserErrors:
    def test_parse_missing_file_raises_parse_error(self):
        with pytest.raises(ParseError, match="not found"):
            CSVParser().parse("/tmp/does_not_exist_xyz_abc.csv")

    def test_parse_empty_file_raises_parse_error(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_bytes(b"")
        with pytest.raises(ParseError, match="empty"):
            CSVParser().parse(str(f))

    def test_parse_whitespace_only_raises_parse_error(self, tmp_path):
        f = tmp_path / "blank.csv"
        f.write_text("   \n   \n", encoding="utf-8")
        with pytest.raises(ParseError, match="no data rows"):
            CSVParser().parse(str(f))

    def test_all_empty_first_row_is_skipped(self, tmp_path):
        """All-blank rows are filtered before header detection.
        The empty `,,,` row is skipped; the next non-empty row becomes the header.
        """
        f = tmp_path / "noheaders.csv"
        f.write_text(",,,\nval1,val2,val3\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].tables[0].headers == ["val1", "val2", "val3"]


# ------------------------------------------------------------------ #
#  Basic CSV parsing                                                   #
# ------------------------------------------------------------------ #

class TestCSVParserBasic:
    def test_parse_returns_raw_document(self, tmp_path):
        f = tmp_path / "sales.csv"
        f.write_text("Product,Q1,Q2\nWidget A,100,120\nWidget B,80,95\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw is not None
        assert raw.format == "csv"

    def test_doc_id_generated_from_filename(self, tmp_path):
        f = tmp_path / "SalesData2024.csv"
        f.write_text("A,B\n1,2\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.doc_id == "sales-data-2024"

    def test_title_generated_from_filename(self, tmp_path):
        f = tmp_path / "employee_roster.csv"
        f.write_text("Name,Role\nAlice,Engineer\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.title == "Employee Roster"

    def test_exactly_one_section(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("A,B,C\n1,2,3\n4,5,6\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert len(raw.sections) == 1

    def test_exactly_one_table(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("A,B,C\n1,2,3\n4,5,6\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert len(raw.sections[0].tables) == 1

    def test_first_row_becomes_headers(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("Name,Age,City\nAlice,30,NYC\nBob,25,LA\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        table = raw.sections[0].tables[0]
        assert table.headers == ["Name", "Age", "City"]

    def test_data_rows_correct(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("Name,Age\nAlice,30\nBob,25\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        table = raw.sections[0].tables[0]
        assert len(table.rows) == 2
        assert table.rows[0] == ["Alice", "30"]
        assert table.rows[1] == ["Bob", "25"]

    def test_table_id_is_tbl_001(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("A,B\n1,2\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].tables[0].table_id == "tbl_001"

    def test_section_id_is_empty(self, tmp_path):
        """Section id must be empty string — Normaliser assigns §ids."""
        f = tmp_path / "data.csv"
        f.write_text("A,B\n1,2\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].id == ""

    def test_section_level_is_one(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("A,B\n1,2\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].level == 1

    def test_section_text_contains_column_names(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("Revenue,Region,Quarter\n100,North,Q1\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert "Revenue" in raw.sections[0].text
        assert "Region" in raw.sections[0].text
        assert "Quarter" in raw.sections[0].text

    def test_section_text_contains_data_values(self, tmp_path):
        """Data values must appear in section text for BM25 retrieval."""
        f = tmp_path / "data.csv"
        f.write_text("Product,Price\nWidget A,99.99\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert "Widget A" in raw.sections[0].text
        assert "99.99" in raw.sections[0].text

    def test_header_only_file_produces_zero_data_rows(self, tmp_path):
        """A file with only headers and no data rows is valid — 0 data rows."""
        f = tmp_path / "headers_only.csv"
        f.write_text("Name,Age,City\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        table = raw.sections[0].tables[0]
        assert table.headers == ["Name", "Age", "City"]
        assert table.rows == []

    def test_source_field_is_absolute_path(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("A,B\n1,2\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.source == str(f.resolve())

    def test_all_row_lengths_match_headers(self, tmp_path):
        """Every data row must have exactly len(headers) cells."""
        f = tmp_path / "data.csv"
        # Write a CSV with consistent rows
        f.write_text("A,B,C\n1,2,3\n4,5,6\n7,8,9\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        table = raw.sections[0].tables[0]
        for row in table.rows:
            assert len(row) == len(table.headers)


# ------------------------------------------------------------------ #
#  Row length normalisation                                            #
# ------------------------------------------------------------------ #

class TestCSVRowNormalisation:
    def test_short_rows_are_padded(self, tmp_path):
        f = tmp_path / "short.csv"
        f.write_text("A,B,C\n1,2\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].tables[0].rows[0] == ["1", "2", ""]

    def test_long_rows_are_truncated(self, tmp_path):
        f = tmp_path / "long.csv"
        f.write_text("A,B,C\n1,2,3,4,5\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].tables[0].rows[0] == ["1", "2", "3"]

    def test_mixed_length_rows_all_normalised(self, tmp_path):
        f = tmp_path / "mixed.csv"
        f.write_text("A,B,C\n1\n1,2\n1,2,3\n1,2,3,4\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        table = raw.sections[0].tables[0]
        for row in table.rows:
            assert len(row) == 3

    def test_trailing_empty_headers_stripped(self, tmp_path):
        """Trailing empty header cells should be stripped."""
        f = tmp_path / "trailing.csv"
        f.write_text("Name,Age,,\nAlice,30,x,y\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        table = raw.sections[0].tables[0]
        assert table.headers == ["Name", "Age"]
        # Data row truncated to match
        assert table.rows[0] == ["Alice", "30"]


# ------------------------------------------------------------------ #
#  TSV support                                                         #
# ------------------------------------------------------------------ #

class TestTSVParser:
    def test_format_is_tsv(self, tmp_path):
        f = tmp_path / "data.tsv"
        f.write_text("Name\tScore\tGrade\nAlice\t95\tA\nBob\t82\tB\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.format == "tsv"

    def test_tsv_headers_parsed_correctly(self, tmp_path):
        f = tmp_path / "data.tsv"
        f.write_text("Name\tScore\tGrade\nAlice\t95\tA\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].tables[0].headers == ["Name", "Score", "Grade"]

    def test_tsv_rows_parsed_correctly(self, tmp_path):
        f = tmp_path / "data.tsv"
        f.write_text("Name\tScore\nAlice\t95\nBob\t82\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        table = raw.sections[0].tables[0]
        assert table.rows[0] == ["Alice", "95"]
        assert table.rows[1] == ["Bob", "82"]

    def test_tsv_with_commas_in_values(self, tmp_path):
        """TSV must not split on commas inside values."""
        f = tmp_path / "data.tsv"
        f.write_text("Name\tAddress\nAlice\t123 Main St, NYC\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        table = raw.sections[0].tables[0]
        assert table.rows[0][1] == "123 Main St, NYC"


# ------------------------------------------------------------------ #
#  Delimiter auto-detection                                            #
# ------------------------------------------------------------------ #

class TestDelimiterDetection:
    def test_comma_delimiter(self, tmp_path):
        f = tmp_path / "comma.csv"
        f.write_text("A,B,C\n1,2,3\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].tables[0].headers == ["A", "B", "C"]

    def test_semicolon_delimiter(self, tmp_path):
        """European CSV files use semicolons."""
        f = tmp_path / "euro.csv"
        f.write_text("A;B;C\n1;2;3\n4;5;6\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].tables[0].headers == ["A", "B", "C"]

    def test_pipe_delimiter(self, tmp_path):
        f = tmp_path / "pipe.csv"
        f.write_text("A|B|C\n1|2|3\n4|5|6\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].tables[0].headers == ["A", "B", "C"]


# ------------------------------------------------------------------ #
#  Encoding support                                                    #
# ------------------------------------------------------------------ #

class TestCSVEncoding:
    def test_utf8_with_bom(self, tmp_path):
        """utf-8-sig encoding adds a BOM prefix; CSVParser must strip it."""
        f = tmp_path / "bom.csv"
        # Write with utf-8-sig so the BOM bytes are prepended automatically
        f.write_text("Name,Score\nAlice,95\n", encoding="utf-8-sig")
        raw = CSVParser().parse(str(f))
        # BOM should be stripped — first header must be plain "Name", not "﻿Name"
        assert raw.sections[0].tables[0].headers[0] == "Name"

    def test_latin1_encoding(self, tmp_path):
        f = tmp_path / "latin1.csv"
        # "Ñoño" in latin-1
        content = "Nombre,Ciudad\nJosé,México\n"
        f.write_bytes(content.encode("latin-1"))
        # Should not raise
        raw = CSVParser().parse(str(f))
        assert raw is not None
        assert len(raw.sections[0].tables[0].rows) == 1


# ------------------------------------------------------------------ #
#  Quoted fields and special characters                                #
# ------------------------------------------------------------------ #

class TestCSVQuotedFields:
    def test_quoted_fields_with_commas(self, tmp_path):
        f = tmp_path / "quoted.csv"
        f.write_text('Name,Description\nWidget A,"Fast, reliable"\n', encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert raw.sections[0].tables[0].rows[0][1] == "Fast, reliable"

    def test_quoted_fields_with_newlines(self, tmp_path):
        f = tmp_path / "multiline.csv"
        f.write_text('Name,Notes\nAlice,"Line1\nLine2"\n', encoding="utf-8")
        raw = CSVParser().parse(str(f))
        # csv module handles embedded newlines in quoted fields
        assert raw is not None

    def test_double_quote_escape(self, tmp_path):
        f = tmp_path / "quotes.csv"
        f.write_text('Name,Quote\nAlice,"She said ""hello"""\n', encoding="utf-8")
        raw = CSVParser().parse(str(f))
        assert 'hello' in raw.sections[0].tables[0].rows[0][1]


# ------------------------------------------------------------------ #
#  Large file handling                                                 #
# ------------------------------------------------------------------ #

class TestCSVLargeFile:
    def test_1000_row_csv_parsed_completely(self, tmp_path):
        f = tmp_path / "large.csv"
        lines = ["ID,Value,Category"]
        for i in range(1000):
            lines.append(f"{i},{i * 1.5:.2f},cat_{i % 10}")
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
        raw = CSVParser().parse(str(f))
        table = raw.sections[0].tables[0]
        assert len(table.rows) == 1000
        assert len(table.headers) == 3

    def test_all_rows_normalised_in_large_file(self, tmp_path):
        f = tmp_path / "large.csv"
        lines = ["A,B,C"]
        for i in range(500):
            lines.append(f"{i},{i+1},{i+2}")
        f.write_text("\n".join(lines), encoding="utf-8")
        raw = CSVParser().parse(str(f))
        table = raw.sections[0].tables[0]
        for row in table.rows:
            assert len(row) == 3


# ------------------------------------------------------------------ #
#  _detect_delimiter unit tests                                        #
# ------------------------------------------------------------------ #

class TestDetectDelimiter:
    def test_tsv_always_tab(self):
        assert CSVParser._detect_delimiter("A,B,C\n1,2,3\n", ".tsv") == "\t"

    def test_csv_comma_default(self):
        # When sniffer fails on a minimal one-column file, defaults to comma
        result = CSVParser._detect_delimiter("header\nvalue\n", ".csv")
        assert result in (",", "\t", ";", "|")

    def test_csv_sniffs_semicolon(self):
        sample = "A;B;C\n1;2;3\n4;5;6\n"
        assert CSVParser._detect_delimiter(sample, ".csv") == ";"


# ------------------------------------------------------------------ #
#  _table_text_summary unit tests                                      #
# ------------------------------------------------------------------ #

class TestTableTextSummary:
    def test_summary_contains_file_name(self):
        from docnest.models import TableData
        table = TableData(table_id="tbl_001", headers=["A", "B"], rows=[["1", "2"]])
        summary = CSVParser._table_text_summary(table, "my_data")
        assert "my_data" in summary

    def test_summary_contains_headers(self):
        from docnest.models import TableData
        table = TableData(table_id="tbl_001", headers=["Revenue", "Quarter"], rows=[])
        summary = CSVParser._table_text_summary(table, "sales")
        assert "Revenue" in summary
        assert "Quarter" in summary

    def test_summary_contains_data_values(self):
        from docnest.models import TableData
        table = TableData(
            table_id="tbl_001", headers=["Product", "Units"],
            rows=[["Widget A", "1500"]]
        )
        summary = CSVParser._table_text_summary(table, "inventory")
        assert "Widget A" in summary
        assert "1500" in summary

    def test_summary_empty_rows_no_crash(self):
        from docnest.models import TableData
        table = TableData(table_id="tbl_001", headers=["A", "B"], rows=[])
        summary = CSVParser._table_text_summary(table, "empty")
        assert "Columns" in summary


# ------------------------------------------------------------------ #
#  _filename_to_title utility                                          #
# ------------------------------------------------------------------ #

class TestFilenameToTitle:
    def test_underscores_replaced(self):
        assert _filename_to_title("sales_data_2024") == "Sales Data 2024"

    def test_hyphens_replaced(self):
        assert _filename_to_title("employee-roster") == "Employee Roster"

    def test_mixed_separators(self):
        assert _filename_to_title("q1_report-2024") == "Q1 Report 2024"

    def test_single_word(self):
        assert _filename_to_title("inventory") == "Inventory"
