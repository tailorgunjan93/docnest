"""Tests for SectionNormaliser — §id assignment and hierarchy.

Run: pytest tests/test_normalizer.py -v
"""
from __future__ import annotations

import pytest

from docnest.models import RawDocument, Section
from docnest.normalizer import SectionNormaliser


# ── Helper ────────────────────────────────────────────────────────────────────

def make_raw(sections: list[tuple[int, str]], text: str = "Content") -> RawDocument:
    return RawDocument(
        doc_id="test",
        title="Test Doc",
        source="test.pdf",
        format="pdf",
        sections=[
            Section(id="", title=title, level=level, text=f"{text} of {title}")
            for level, title in sections
        ],
    )


# ── §id assignment ────────────────────────────────────────────────────────────

class TestSectionIds:
    def test_flat_top_level(self):
        raw = make_raw([(1, "Intro"), (1, "Methods"), (1, "Results")])
        doc = SectionNormaliser().normalise(raw)
        assert [s.id for s in doc.sections] == ["§1", "§2", "§3"]

    def test_two_level_nesting(self):
        raw = make_raw([(1, "Intro"), (2, "Background"), (2, "Scope"), (1, "Methods")])
        doc = SectionNormaliser().normalise(raw)
        assert [s.id for s in doc.sections] == ["§1", "§1.1", "§1.2", "§2"]

    def test_three_level_nesting(self):
        raw = make_raw([(1, "A"), (2, "A.1"), (3, "A.1.1"), (3, "A.1.2"), (2, "A.2")])
        doc = SectionNormaliser().normalise(raw)
        assert [s.id for s in doc.sections] == ["§1", "§1.1", "§1.1.1", "§1.1.2", "§1.2"]

    def test_counter_resets_on_new_parent(self):
        raw = make_raw([(1, "A"), (2, "A.1"), (1, "B"), (2, "B.1")])
        doc = SectionNormaliser().normalise(raw)
        assert [s.id for s in doc.sections] == ["§1", "§1.1", "§2", "§2.1"]

    def test_six_levels_deep(self):
        raw = make_raw([(1, "L1"), (2, "L2"), (3, "L3"), (4, "L4"), (5, "L5"), (6, "L6")])
        doc = SectionNormaliser().normalise(raw)
        assert doc.sections[-1].id == "§1.1.1.1.1.1"

    def test_level_jump_h1_to_h3(self):
        """Missing H2 — should not crash; H3 treated as child of H1."""
        raw = make_raw([(1, "Top"), (3, "Deep")])
        doc = SectionNormaliser().normalise(raw)
        assert doc.sections[0].id == "§1"
        assert doc.sections[1].id.startswith("§1.")

    def test_single_section(self):
        raw = make_raw([(1, "Only")])
        doc = SectionNormaliser().normalise(raw)
        assert doc.sections[0].id == "§1"

    def test_empty_document(self):
        raw = make_raw([])
        doc = SectionNormaliser().normalise(raw)
        assert doc.sections == []


# ── Parent / child links ──────────────────────────────────────────────────────

class TestParentChildLinks:
    def test_h2_parent_is_h1(self):
        raw = make_raw([(1, "A"), (2, "A.1"), (2, "A.2")])
        doc = SectionNormaliser().normalise(raw)
        assert doc.sections[1].parent_id == "§1"
        assert doc.sections[2].parent_id == "§1"

    def test_h1_has_no_parent(self):
        raw = make_raw([(1, "A"), (2, "B")])
        doc = SectionNormaliser().normalise(raw)
        assert doc.sections[0].parent_id is None

    def test_children_listed_on_parent(self):
        raw = make_raw([(1, "A"), (2, "A.1"), (2, "A.2")])
        doc = SectionNormaliser().normalise(raw)
        assert "§1.1" in doc.sections[0].children
        assert "§1.2" in doc.sections[0].children

    def test_leaf_has_no_children(self):
        raw = make_raw([(1, "A"), (2, "A.1")])
        doc = SectionNormaliser().normalise(raw)
        assert doc.sections[1].children == []

    def test_multiple_top_level_sections_each_track_own_children(self):
        raw = make_raw([(1, "A"), (2, "A.1"), (1, "B"), (2, "B.1")])
        doc = SectionNormaliser().normalise(raw)
        assert "§1.1" in doc.sections[0].children
        assert "§2.1" in doc.sections[2].children
        assert doc.sections[0].children == ["§1.1"]
        assert doc.sections[2].children == ["§2.1"]


# ── Token counting ────────────────────────────────────────────────────────────

class TestTokenCount:
    def test_non_zero_for_non_empty_text(self):
        raw = make_raw([(1, "Intro")], text="This is some content text")
        doc = SectionNormaliser().normalise(raw)
        assert doc.sections[0].token_count > 0

    def test_zero_for_empty_text(self):
        raw = RawDocument(
            doc_id="t", title="T", source="f.pdf", format="pdf",
            sections=[Section(id="", title="Empty", level=1, text="")]
        )
        doc = SectionNormaliser().normalise(raw)
        assert doc.sections[0].token_count == 0

    def test_longer_text_has_more_tokens(self):
        short_raw = make_raw([(1, "S")], text="Short")
        long_raw = make_raw([(1, "L")], text="Much longer text with many more words here")
        short_doc = SectionNormaliser().normalise(short_raw)
        long_doc = SectionNormaliser().normalise(long_raw)
        assert long_doc.sections[0].token_count > short_doc.sections[0].token_count


# ── Table normalisation ───────────────────────────────────────────────────────

class TestTableNormalisation:
    def test_rows_padded_to_match_headers(self):
        """Rows shorter than headers should be padded."""
        from docnest.models import TableData
        s = Section(
            id="", title="Data", level=1, text="",
            tables=[
                TableData(
                    table_id="t1",
                    headers=["A", "B", "C"],
                    rows=[["1", "2"]],   # only 2 cols, should become 3
                )
            ],
        )
        raw = RawDocument(doc_id="t", title="T", source="f", format="pdf", sections=[s])
        doc = SectionNormaliser().normalise(raw)
        assert all(len(row) == 3 for row in doc.sections[0].tables[0].rows)

    def test_rows_truncated_when_longer_than_headers(self):
        """Rows longer than headers should be truncated to header count (line 79)."""
        from docnest.models import TableData
        s = Section(
            id="", title="Data", level=1, text="",
            tables=[TableData(table_id="t1", headers=["A", "B"],
                              rows=[["1", "2", "3", "EXTRA"]])]
        )
        raw = RawDocument(doc_id="t", title="T", source="f", format="pdf", sections=[s])
        doc = SectionNormaliser().normalise(raw)
        assert all(len(row) == 2 for row in doc.sections[0].tables[0].rows)

    def test_table_with_empty_headers_rows_unchanged(self):
        """Table with 0 headers → skip normalization (line 73 continue)."""
        from docnest.models import TableData
        s = Section(
            id="", title="Data", level=1, text="",
            tables=[TableData(table_id="t1", headers=[], rows=[["a", "b", "c"]])]
        )
        raw = RawDocument(doc_id="t", title="T", source="f", format="pdf", sections=[s])
        doc = SectionNormaliser().normalise(raw)
        # Rows stay unchanged since there are no headers to define width
        assert doc.sections[0].tables[0].rows == [["a", "b", "c"]]

    def test_rows_with_correct_length_unchanged(self):
        from docnest.models import TableData
        s = Section(
            id="", title="Data", level=1, text="",
            tables=[TableData(table_id="t1", headers=["A", "B"], rows=[["1", "2"], ["3", "4"]])]
        )
        raw = RawDocument(doc_id="t", title="T", source="f", format="pdf", sections=[s])
        doc = SectionNormaliser().normalise(raw)
        assert doc.sections[0].tables[0].rows == [["1", "2"], ["3", "4"]]


# ── Document-level fields ─────────────────────────────────────────────────────

class TestDocumentOutput:
    def test_normalise_returns_document(self):
        from docnest.models import Document
        raw = make_raw([(1, "Intro")])
        doc = SectionNormaliser().normalise(raw)
        assert isinstance(doc, Document)

    def test_doc_id_preserved(self):
        raw = make_raw([(1, "Intro")])
        doc = SectionNormaliser().normalise(raw)
        assert doc.doc_id == "test"

    def test_title_preserved(self):
        raw = make_raw([(1, "Intro")])
        doc = SectionNormaliser().normalise(raw)
        assert doc.title == "Test Doc"

    def test_section_count_matches_input(self):
        raw = make_raw([(1, "A"), (2, "B"), (2, "C"), (1, "D")])
        doc = SectionNormaliser().normalise(raw)
        assert len(doc.sections) == 4
