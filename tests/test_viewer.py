"""Tests for docnest.viewer — HTML generation from .udf archives.

Run: pytest tests/test_viewer.py -v
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from docnest.viewer import (
    generate_html,
    _e,
    _render_table,
    _render_section_content,
    _build_sidebar,
    _build_doc_body,
    _render,
)


# ── generate_html ─────────────────────────────────────────────────────────────

class TestGenerateHtml:
    def test_returns_string_path(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        result = generate_html(str(minimal_udf), out)
        assert isinstance(result, str)

    def test_creates_html_file(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        generate_html(str(minimal_udf), out)
        assert Path(out).exists()

    def test_default_output_same_dir_as_udf(self, minimal_udf: Path):
        """No output_path → .html placed next to .udf."""
        result = generate_html(str(minimal_udf))
        assert result.endswith(".html")
        html_path = Path(result)
        assert html_path.exists()
        assert html_path.parent == minimal_udf.parent

    def test_missing_file_raises_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            generate_html(str(tmp_path / "missing.udf"))

    def test_html_contains_doctype(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        generate_html(str(minimal_udf), out)
        content = Path(out).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_html_contains_document_title(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        generate_html(str(minimal_udf), out)
        content = Path(out).read_text(encoding="utf-8")
        assert "Test Document" in content

    def test_html_contains_section_ids(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        generate_html(str(minimal_udf), out)
        content = Path(out).read_text(encoding="utf-8")
        assert "§1" in content

    def test_html_contains_summary(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        generate_html(str(minimal_udf), out)
        content = Path(out).read_text(encoding="utf-8")
        assert "Test document summary." in content

    def test_html_contains_insights(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        generate_html(str(minimal_udf), out)
        content = Path(out).read_text(encoding="utf-8")
        assert "Insight one" in content

    def test_html_contains_key_numbers(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        generate_html(str(minimal_udf), out)
        content = Path(out).read_text(encoding="utf-8")
        assert "Count" in content  # the label from minimal_udf key_numbers

    def test_html_contains_keyword_badges(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        generate_html(str(minimal_udf), out)
        content = Path(out).read_text(encoding="utf-8")
        assert "kw-badge" in content

    def test_html_is_utf8_encoded(self, minimal_udf: Path, tmp_path: Path):
        out = str(tmp_path / "out.html")
        generate_html(str(minimal_udf), out)
        # Should be readable as UTF-8 without errors
        content = Path(out).read_text(encoding="utf-8")
        assert len(content) > 100

    def test_custom_output_path_honoured(self, minimal_udf: Path, tmp_path: Path):
        custom = str(tmp_path / "custom_name.html")
        generate_html(str(minimal_udf), custom)
        assert Path(custom).exists()

    def test_html_with_tables(self, tmp_path: Path):
        """A UDF with table data should render table HTML."""
        from docnest.models import Document, RawDocument, Section, TableData
        from docnest.normalizer import SectionNormaliser
        from docnest.quantizer import Quantizer
        from docnest.writer import UDFWriter
        from tests.conftest import MockEmbedder

        raw = RawDocument(
            doc_id="tbl-doc", title="Table Doc", source="t.md", format="md",
            sections=[Section(id="", title="Data", level=1, text="Some text.")]
        )
        doc = SectionNormaliser().normalise(raw)
        doc.sections[0].tables = [
            TableData(
                table_id="t1",
                caption="Demo Table",
                headers=["Col A", "Col B"],
                rows=[["1", "2"], ["3", "4"]],
            )
        ]
        doc.sections[0].summary = "Data section."
        doc.sections[0].keywords = ["data"]
        doc.summary = "Table document."

        udf_path = str(tmp_path / "table.udf")
        UDFWriter(MockEmbedder(), Quantizer("float16")).write(doc, udf_path)
        html_out = str(tmp_path / "table.html")
        generate_html(udf_path, html_out)
        content = Path(html_out).read_text(encoding="utf-8")
        assert "Col A" in content
        assert "Col B" in content


# ── _e (HTML escape) ─────────────────────────────────────────────────────────

class TestHtmlEscape:
    def test_escapes_angle_brackets(self):
        assert "&lt;" in _e("<")
        assert "&gt;" in _e(">")

    def test_escapes_ampersand(self):
        assert "&amp;" in _e("&")

    def test_escapes_double_quotes(self):
        assert "&quot;" in _e('"')

    def test_plain_text_unchanged(self):
        assert _e("hello world 123") == "hello world 123"

    def test_converts_non_string_to_str(self):
        result = _e(42)
        assert result == "42"

    def test_xss_payload_neutralised(self):
        payload = "<script>alert('xss')</script>"
        result = _e(payload)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result


# ── _render_table ─────────────────────────────────────────────────────────────

class TestRenderTable:
    def test_renders_table_element(self):
        html = _render_table({"headers": ["A"], "rows": [], "table_id": "t1"})
        assert "<table>" in html

    def test_renders_header_cells(self):
        html = _render_table({"headers": ["Col A", "Col B"], "rows": [], "table_id": "t1"})
        assert "<th>" in html
        assert "Col A" in html
        assert "Col B" in html

    def test_renders_data_rows(self):
        html = _render_table({
            "headers": ["X"],
            "rows": [["val1"], ["val2"]],
            "table_id": "t1",
        })
        assert "val1" in html
        assert "val2" in html

    def test_caption_from_caption_field(self):
        html = _render_table({"headers": [], "rows": [], "caption": "My Caption", "table_id": "t1"})
        assert "My Caption" in html

    def test_table_id_used_as_caption_fallback(self):
        html = _render_table({"headers": [], "rows": [], "table_id": "my-table"})
        assert "my-table" in html

    def test_empty_table_no_crash(self):
        html = _render_table({})
        assert "<table>" in html

    def test_html_escapes_header_content(self):
        html = _render_table({"headers": ["<b>Bad</b>"], "rows": [], "table_id": "t1"})
        assert "<b>Bad</b>" not in html
        assert "&lt;b&gt;" in html

    def test_html_escapes_cell_content(self):
        html = _render_table({"headers": ["H"], "rows": [["<script>"]], "table_id": "t1"})
        assert "<script>" not in html


# ── _render_section_content ───────────────────────────────────────────────────

class TestRenderSectionContent:
    def test_text_rendered(self):
        html = _render_section_content({"text": "Hello world"})
        assert "Hello world" in html

    def test_empty_section_returns_empty_string(self):
        html = _render_section_content({})
        assert html == ""

    def test_tables_rendered(self):
        sec = {
            "text": "body text",
            "tables": [{"headers": ["Col"], "rows": [["val"]], "table_id": "t1"}],
        }
        html = _render_section_content(sec)
        assert "Col" in html
        assert "val" in html

    def test_newlines_converted_to_br(self):
        html = _render_section_content({"text": "line1\nline2"})
        assert "<br>" in html

    def test_no_tables_key_no_crash(self):
        html = _render_section_content({"text": "just text"})
        assert "just text" in html


# ── _build_sidebar ────────────────────────────────────────────────────────────

class TestBuildSidebar:
    def test_returns_string(self):
        idx = [{"id": "§1", "title": "Intro", "level": 1}]
        assert isinstance(_build_sidebar(idx), str)

    def test_contains_section_id(self):
        idx = [{"id": "§1", "title": "Intro", "level": 1}]
        html = _build_sidebar(idx)
        assert "§1" in html

    def test_contains_title(self):
        idx = [{"id": "§1", "title": "Introduction", "level": 1}]
        html = _build_sidebar(idx)
        assert "Introduction" in html

    def test_multiple_sections(self):
        idx = [
            {"id": "§1", "title": "A", "level": 1},
            {"id": "§1.1", "title": "B", "level": 2},
        ]
        html = _build_sidebar(idx)
        assert "§1.1" in html

    def test_empty_index(self):
        html = _build_sidebar([])
        assert html == ""

    def test_level_class_applied(self):
        idx = [{"id": "§1", "title": "A", "level": 2}]
        html = _build_sidebar(idx)
        assert "toc-l2" in html


# ── _build_doc_body ───────────────────────────────────────────────────────────

class TestBuildDocBody:
    def test_section_text_rendered(self):
        idx = [{"id": "§1", "title": "Intro", "level": 1}]
        sections = {"§1": {"text": "Hello content"}}
        html = _build_doc_body(idx, sections)
        assert "Hello content" in html

    def test_missing_section_content_no_crash(self):
        idx = [{"id": "§1", "title": "Intro", "level": 1}]
        html = _build_doc_body(idx, {})
        assert "§1" in html

    def test_summary_included_in_body(self):
        idx = [{"id": "§1", "title": "A", "level": 1, "summary": "Nice summary."}]
        html = _build_doc_body(idx, {})
        assert "Nice summary." in html

    def test_keywords_rendered_as_badges(self):
        idx = [{"id": "§1", "title": "A", "level": 1, "keywords": ["alpha", "beta"]}]
        html = _build_doc_body(idx, {})
        assert "alpha" in html
        assert "beta" in html

    def test_empty_index(self):
        html = _build_doc_body([], {})
        assert html == ""

    def test_heading_level_adjusted(self):
        """§1 → h2 (level+1), §1.1 → h3."""
        idx = [{"id": "§1", "title": "A", "level": 1}]
        html = _build_doc_body(idx, {})
        assert "<h2" in html

    def test_section_id_anchor_present(self):
        idx = [{"id": "§2", "title": "B", "level": 1}]
        html = _build_doc_body(idx, {})
        assert 'id="§2"' in html or "§2" in html


# ── Full render edge cases ────────────────────────────────────────────────────

class TestRenderFunction:
    def _minimal_manifest(self) -> dict:
        return {
            "udf_version": "1.0",
            "doc_id": "test",
            "title": "Test",
            "embedding_model": "mock",
            "quantization": "float16",
            "created_at": "2026-01-01T00:00:00",
        }

    def _minimal_catalogue(self) -> dict:
        return {
            "doc_id": "test",
            "title": "Test",
            "summary": "A test document.",
            "insights": ["Insight A."],
            "key_numbers": [{"label": "Count", "value": "5", "unit": None, "section": "§1"}],
            "section_index": [
                {"id": "§1", "title": "Intro", "level": 1, "keywords": ["intro"], "summary": "Intro summary."}
            ],
        }

    def _minimal_content(self) -> dict:
        return {"doc_id": "test", "sections": {"§1": {"text": "Section text here."}}}

    def test_render_returns_html_string(self):
        html = _render(
            self._minimal_manifest(),
            self._minimal_catalogue(),
            self._minimal_content(),
            "test.udf",
        )
        assert "<!DOCTYPE html>" in html

    def test_render_includes_meta_bar_when_owner_set(self):
        cat = self._minimal_catalogue()
        cat["owner"] = "Alice"
        html = _render(self._minimal_manifest(), cat, self._minimal_content(), "test.udf")
        assert "Alice" in html

    def test_render_includes_tags(self):
        cat = self._minimal_catalogue()
        cat["tags"] = ["q4", "finance"]
        html = _render(self._minimal_manifest(), cat, self._minimal_content(), "test.udf")
        assert "q4" in html

    def test_render_handles_empty_sections(self):
        cat = self._minimal_catalogue()
        cat["section_index"] = []
        html = _render(self._minimal_manifest(), cat, {"doc_id": "test", "sections": {}}, "test.udf")
        assert "<!DOCTYPE html>" in html

    def test_render_escapes_xss_in_title(self):
        cat = self._minimal_catalogue()
        cat["title"] = "<script>evil()</script>"
        html = _render(self._minimal_manifest(), cat, self._minimal_content(), "test.udf")
        assert "<script>evil()" not in html
