"""Deterministic keyword extraction (test-first).

FAILS until docnest/keywords.py lands. Populates section.keywords WITHOUT an LLM so the
reader's BM25/keyword index ranks sections (currently empty → hybrid search returns nothing
→ queries fall to Layer 4). Enables Layer 1/2 routing.

Run: pytest tests/test_keywords.py -v
"""
from __future__ import annotations

from docnest.models import Document, Section


_TEXT = ("Selenium and Playwright test suites now cover 87% of critical user journeys. "
         "Regression test time dropped from 4 hours to 38 minutes thanks to parallel "
         "execution on GitHub Actions.")


class TestExtractKeywords:
    def test_returns_salient_terms(self):
        from docnest.keywords import extract_keywords
        kws = extract_keywords(_TEXT, "Test Automation", k=8)
        low = {w.lower() for w in kws}
        assert "selenium" in low or "playwright" in low
        assert "test" in low or "regression" in low
        assert len(kws) <= 8

    def test_drops_stopwords_and_short_tokens(self):
        from docnest.keywords import extract_keywords
        kws = {w.lower() for w in extract_keywords("the of a to and is on at by", "T", k=8)}
        assert not (kws & {"the", "of", "a", "to", "and", "is", "on", "at", "by"})

    def test_deterministic(self):
        from docnest.keywords import extract_keywords
        assert extract_keywords(_TEXT, "T") == extract_keywords(_TEXT, "T")

    def test_empty_text_uses_title(self):
        from docnest.keywords import extract_keywords
        kws = {w.lower() for w in extract_keywords("", "Cloud Infrastructure", k=8)}
        assert "cloud" in kws or "infrastructure" in kws


class TestEnrichKeywords:
    def test_fills_section_keywords(self):
        from docnest.keywords import enrich_keywords
        doc = Document(doc_id="d", title="t", source="x", format="md",
                       sections=[Section(id="§1", title="Test Automation", level=1, text=_TEXT)])
        assert not doc.sections[0].keywords
        enrich_keywords(doc)
        assert doc.sections[0].keywords

    def test_noop_when_already_populated(self):
        from docnest.keywords import enrich_keywords
        doc = Document(doc_id="d", title="t", source="x", format="md",
                       sections=[Section(id="§1", title="S", level=1, text=_TEXT,
                                         keywords=["existing"])])
        enrich_keywords(doc)
        assert doc.sections[0].keywords == ["existing"]


class TestExtractiveAnswer:
    """Layer-1 extractive answering: the question-relevant sentence, at 0 tokens."""

    def test_returns_answer_bearing_sentence(self):
        from docnest.reader import _best_sentences
        out = _best_sentences(_TEXT, "what percentage of critical user journeys do tests cover?", n=1)
        assert "87%" in out

    def test_empty_when_no_overlap(self):
        from docnest.reader import _best_sentences
        assert _best_sentences(_TEXT, "quarterly dividend payout ratio", n=1) == ""

    def test_empty_text(self):
        from docnest.reader import _best_sentences
        assert _best_sentences("", "anything", n=1) == ""
