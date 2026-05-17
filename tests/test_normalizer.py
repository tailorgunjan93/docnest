"""Tests for SectionNormaliser — §id assignment and hierarchy.

Phase: 1  |  Issue: #2  |  Run: pytest tests/test_normalizer.py -v
"""
import pytest
from DOCNEST.normalizer import SectionNormaliser
from DOCNEST.models import RawDocument, Section


def make_raw(sections: list[tuple[int, str]]) -> RawDocument:
    """Helper: build a RawDocument from (level, title) pairs."""
    return RawDocument(
        doc_id="test",
        title="Test Doc",
        source="test.pdf",
        format="pdf",
        sections=[
            Section(id="", title=title, level=level, text=f"Content of {title}")
            for level, title in sections
        ],
    )


class TestSectionNormaliser:
    """TODO (Phase 1): Uncomment after SectionNormaliser is implemented."""

    # def test_assigns_top_level_ids(self):
    #     raw = make_raw([(1, "Intro"), (1, "Methods"), (1, "Results")])
    #     doc = SectionNormaliser().normalise(raw)
    #     ids = [s.id for s in doc.sections]
    #     assert ids == ["§1", "§2", "§3"]

    # def test_assigns_nested_ids(self):
    #     raw = make_raw([(1, "Intro"), (2, "Background"), (2, "Scope"), (1, "Methods")])
    #     doc = SectionNormaliser().normalise(raw)
    #     ids = [s.id for s in doc.sections]
    #     assert ids == ["§1", "§1.1", "§1.2", "§2"]

    # def test_parent_links_are_correct(self):
    #     raw = make_raw([(1, "A"), (2, "A.1"), (2, "A.2")])
    #     doc = SectionNormaliser().normalise(raw)
    #     assert doc.sections[1].parent_id == "§1"
    #     assert doc.sections[2].parent_id == "§1"

    # def test_children_links_are_correct(self):
    #     raw = make_raw([(1, "A"), (2, "A.1"), (2, "A.2")])
    #     doc = SectionNormaliser().normalise(raw)
    #     assert "§1.1" in doc.sections[0].children
    #     assert "§1.2" in doc.sections[0].children

    # def test_resets_counter_on_new_top_level(self):
    #     raw = make_raw([(1, "A"), (2, "A.1"), (1, "B"), (2, "B.1")])
    #     doc = SectionNormaliser().normalise(raw)
    #     ids = [s.id for s in doc.sections]
    #     assert ids == ["§1", "§1.1", "§2", "§2.1"]

    pass
