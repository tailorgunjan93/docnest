"""Complex Tables · Step 2 — PyMuPDF native table extraction (test-first).

FAILS until PyMuPDFParser learns find_tables(). Pins step2-DESIGN.md /
step2-IMPACT-RISK.md: the fast PDF path must populate section.tables from a
bordered table, without duplicating cell text in prose, gated by extract_tables.

Skips cleanly if PyMuPDF is not installed.

Run: pytest tests/test_pymupdf_tables.py -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz", reason="PyMuPDF not installed")

from docnest.parsers.pymupdf_pdf import PyMuPDFParser  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "sample_text.pdf"


def _ensure_sample() -> str:
    if not FIXTURE.exists():
        import importlib.util
        gen = Path(__file__).parent / "fixtures" / "_make_sample_pdf.py"
        spec = importlib.util.spec_from_file_location("_mk", gen)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod.main()
    return str(FIXTURE)


def _all_tables(raw):
    return [t for s in raw.sections for t in s.tables]


class TestPyMuPDFTableExtraction:
    def test_table_extracted_with_headers_and_rows(self):
        raw = PyMuPDFParser(extract_tables=True).parse(_ensure_sample())
        tables = _all_tables(raw)
        assert tables, "expected at least one TableData from the bordered sample table"
        t = tables[0]
        assert t.headers == ["Region", "Q1", "Q2", "Q3"]
        assert len(t.rows) == 3
        assert ["Europe", "38.1", "41.0", "45.2"] in t.rows

    def test_table_attached_to_a_section(self):
        raw = PyMuPDFParser(extract_tables=True).parse(_ensure_sample())
        holder = [s for s in raw.sections if s.tables]
        assert holder, "the table must be attached to a section"

    def test_cell_text_not_duplicated_in_prose(self):
        raw = PyMuPDFParser(extract_tables=True).parse(_ensure_sample())
        holder = [s for s in raw.sections if s.tables][0]
        # 'Europe' / '38.1' live only in the table, not the section prose
        assert "Europe" not in holder.text
        assert "38.1" not in holder.text

    def test_flag_off_extracts_no_tables(self):
        raw = PyMuPDFParser(extract_tables=False).parse(_ensure_sample())
        assert _all_tables(raw) == []

    def test_table_free_pdf_unaffected(self, tmp_path):
        # A PDF with headings + prose but no ruled table → no tables, no error.
        p = tmp_path / "notable.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 80), "Overview", fontsize=20, fontname="hebo")
        page.insert_text((72, 120), "This document has no tables at all.", fontsize=11)
        doc.save(str(p)); doc.close()
        raw = PyMuPDFParser(extract_tables=True).parse(str(p))
        assert _all_tables(raw) == []
        assert any(s.text for s in raw.sections)
