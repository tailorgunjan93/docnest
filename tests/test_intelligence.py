"""Tests for IntelligenceEngine — LLM-powered document enrichment.

Run: pytest tests/test_intelligence.py -v
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from docnest.intelligence import IntelligenceEngine, _extract_json
from docnest.models import Document, Section, KeyNumber, RawDocument
from docnest.normalizer import SectionNormaliser
from docnest.exceptions import IntelligenceError
from docnest.providers.llm import ILLMProvider
from tests.conftest import MockLLMProvider


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_doc(n: int = 2, long_text: bool = True) -> Document:
    """Build a normalised Document with n sections."""
    text = "word " * 50 if long_text else "short"
    raw = RawDocument(
        doc_id="test",
        title="Test Doc",
        source="test.md",
        format="md",
        sections=[
            Section(id="", title=f"Section {i+1}", level=1, text=f"{text} about section {i+1}")
            for i in range(n)
        ],
    )
    return SectionNormaliser().normalise(raw)


class _JsonLLM(ILLMProvider):
    """Returns the payload as JSON for every complete() call."""

    def __init__(self, payload: Any) -> None:
        self._payload = payload

    @property
    def provider_name(self) -> str:
        return "json"

    @property
    def model_name(self) -> str:
        return "json-model"

    def complete(self, prompt: str, system: str = "",
                 temperature: float = 0.1, max_tokens: int = 512) -> str:
        if isinstance(self._payload, str):
            return self._payload
        return json.dumps(self._payload)


class _AlternatingLLM(ILLMProvider):
    """Odd calls return a summary string; even calls return keyword JSON."""

    def __init__(self) -> None:
        self._n: int = 0

    @property
    def provider_name(self) -> str:
        return "alt"

    @property
    def model_name(self) -> str:
        return "alt-model"

    def complete(self, prompt: str, system: str = "",
                 temperature: float = 0.1, max_tokens: int = 512) -> str:
        self._n += 1
        if self._n % 2 == 1:
            return "One sentence summary about the section."
        return '["alpha", "beta", "gamma", "delta", "epsilon"]'


class _RaisingLLM(ILLMProvider):
    """Always raises IntelligenceError."""

    @property
    def provider_name(self) -> str:
        return "err"

    @property
    def model_name(self) -> str:
        return "err-model"

    def complete(self, prompt: str, system: str = "",
                 temperature: float = 0.1, max_tokens: int = 512) -> str:
        raise IntelligenceError("LLM failed deliberately.")


# ── IntelligenceEngine init ───────────────────────────────────────────────────

class TestIntelligenceEngineInit:
    def test_init_with_provider_instance(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        assert engine.provider == "mock"
        assert engine.model == "mock-model"

    def test_init_stores_api_key(self):
        engine = IntelligenceEngine(provider=MockLLMProvider(), api_key="sk-test")
        assert engine.api_key == "sk-test"

    def test_provider_attr_accessible(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        assert engine.provider is not None


# ── enrich_sections ───────────────────────────────────────────────────────────

class TestEnrichSections:
    def test_short_sections_get_title_as_summary(self):
        """Sections with < 20 words get title as summary (no LLM call)."""
        engine = IntelligenceEngine(provider=MockLLMProvider())
        raw = RawDocument(
            doc_id="x", title="X", source="x.md", format="md",
            sections=[Section(id="", title="Short Section", level=1, text="too short")]
        )
        doc = SectionNormaliser().normalise(raw)
        result = engine.enrich_sections(doc)
        assert result.sections[0].summary == "Short Section"

    def test_short_section_keywords_from_title(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        raw = RawDocument(
            doc_id="x", title="X", source="x.md", format="md",
            sections=[Section(id="", title="Short Title", level=1, text="brief")]
        )
        doc = SectionNormaliser().normalise(raw)
        result = engine.enrich_sections(doc)
        assert isinstance(result.sections[0].keywords, list)
        assert len(result.sections[0].keywords) > 0

    def test_long_section_calls_llm_for_summary(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        doc = make_doc(1, long_text=True)
        result = engine.enrich_sections(doc)
        # MockLLMProvider.complete() returns "Mock answer from LLM."
        assert result.sections[0].summary == "Mock answer from LLM."

    def test_long_section_keywords_are_list(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        doc = make_doc(1, long_text=True)
        result = engine.enrich_sections(doc)
        assert isinstance(result.sections[0].keywords, list)

    def test_keyword_json_parsed_from_llm(self):
        """When keyword call returns a valid JSON array, use it."""
        engine = IntelligenceEngine(provider=_AlternatingLLM())
        doc = make_doc(1, long_text=True)
        result = engine.enrich_sections(doc)
        assert "alpha" in result.sections[0].keywords

    def test_keyword_fallback_on_non_json_response(self):
        """Non-JSON keyword response falls back to title/summary word split."""
        engine = IntelligenceEngine(provider=MockLLMProvider())
        doc = make_doc(1, long_text=True)
        result = engine.enrich_sections(doc)
        kws = result.sections[0].keywords
        assert isinstance(kws, list)
        assert len(kws) > 0

    def test_multiple_sections_all_enriched(self):
        engine = IntelligenceEngine(provider=_AlternatingLLM())
        doc = make_doc(3, long_text=True)
        result = engine.enrich_sections(doc)
        for sec in result.sections:
            assert sec.summary
            assert isinstance(sec.keywords, list)

    def test_empty_document_no_crash(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        raw = RawDocument(doc_id="x", title="X", source="x.md", format="md", sections=[])
        doc = SectionNormaliser().normalise(raw)
        result = engine.enrich_sections(doc)
        assert result.sections == []

    def test_intelligence_error_degrades_gracefully(self):
        """IntelligenceError from LLM → fallback: title as summary, empty keywords."""
        engine = IntelligenceEngine(provider=_RaisingLLM())
        doc = make_doc(1, long_text=True)
        result = engine.enrich_sections(doc)
        assert result.sections[0].summary == result.sections[0].title
        assert result.sections[0].keywords == []

    def test_returns_same_document_object(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        doc = make_doc(1, long_text=True)
        result = engine.enrich_sections(doc)
        assert result is doc


# ── enrich_document ───────────────────────────────────────────────────────────

class TestEnrichDocument:
    def _make_enriched_doc(self) -> Document:
        doc = make_doc(2, long_text=True)
        for s in doc.sections:
            s.summary = f"Summary of {s.title}."
        return doc

    def test_summary_populated_from_llm(self):
        llm = _JsonLLM({"summary": "Great document.", "insights": [], "key_numbers": []})
        engine = IntelligenceEngine(provider=llm)
        doc = self._make_enriched_doc()
        result = engine.enrich_document(doc)
        assert result.summary == "Great document."

    def test_insights_populated(self):
        llm = _JsonLLM({"summary": "s", "insights": ["Insight A.", "Insight B."], "key_numbers": []})
        engine = IntelligenceEngine(provider=llm)
        doc = self._make_enriched_doc()
        result = engine.enrich_document(doc)
        assert result.insights == ["Insight A.", "Insight B."]

    def test_key_numbers_populated(self):
        payload = {
            "summary": "s", "insights": [],
            "key_numbers": [
                {"label": "Revenue", "value": "$10M", "unit": "USD", "section": "§1"},
                {"label": "Users", "value": "50K", "unit": None, "section": "§2"},
            ],
        }
        engine = IntelligenceEngine(provider=_JsonLLM(payload))
        doc = self._make_enriched_doc()
        result = engine.enrich_document(doc)
        assert len(result.key_numbers) == 2
        assert result.key_numbers[0].label == "Revenue"
        assert isinstance(result.key_numbers[0], KeyNumber)

    def test_key_number_missing_label_skipped(self):
        """key_numbers without label or value are filtered out."""
        payload = {
            "summary": "s", "insights": [],
            "key_numbers": [
                {"label": "", "value": "5", "unit": None, "section": "§1"},  # empty label
                {"label": "Good", "value": "10", "unit": None, "section": "§1"},
            ],
        }
        engine = IntelligenceEngine(provider=_JsonLLM(payload))
        doc = self._make_enriched_doc()
        result = engine.enrich_document(doc)
        assert len(result.key_numbers) == 1
        assert result.key_numbers[0].label == "Good"

    def test_invalid_json_falls_back(self):
        """Bad JSON from LLM → IntelligenceError → fallback summary."""
        engine = IntelligenceEngine(provider=_JsonLLM("not json at all %%##"))
        doc = self._make_enriched_doc()
        result = engine.enrich_document(doc)
        assert "Test Doc" in result.summary
        assert result.insights == []
        assert result.key_numbers == []

    def test_intelligence_error_from_llm_falls_back(self):
        engine = IntelligenceEngine(provider=_RaisingLLM())
        doc = self._make_enriched_doc()
        result = engine.enrich_document(doc)
        assert result.summary.startswith("Document:")
        assert result.insights == []

    def test_returns_same_document_object(self):
        llm = _JsonLLM({"summary": "s", "insights": [], "key_numbers": []})
        engine = IntelligenceEngine(provider=llm)
        doc = self._make_enriched_doc()
        result = engine.enrich_document(doc)
        assert result is doc

    def test_enrich_empty_document_no_crash(self):
        llm = _JsonLLM({"summary": "Empty.", "insights": [], "key_numbers": []})
        engine = IntelligenceEngine(provider=llm)
        raw = RawDocument(doc_id="x", title="Empty", source="x.md", format="md", sections=[])
        doc = SectionNormaliser().normalise(raw)
        result = engine.enrich_document(doc)
        assert result.summary == "Empty."


# ── _build_doc_context ────────────────────────────────────────────────────────

class TestBuildDocContext:
    def test_context_contains_title(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        doc = make_doc(2)
        ctx = engine._build_doc_context(doc)
        assert "Test Doc" in ctx

    def test_context_contains_section_ids(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        doc = make_doc(2)
        ctx = engine._build_doc_context(doc)
        assert "§" in ctx

    def test_context_respects_max_length(self):
        """Long docs get truncated before _MAX_DOC_CONTEXT_CHARS."""
        engine = IntelligenceEngine(provider=MockLLMProvider())
        doc = make_doc(100, long_text=True)
        for s in doc.sections:
            s.summary = "x" * 200
        ctx = engine._build_doc_context(doc)
        # Should be less than the internal cap (8000 chars) plus some header
        assert len(ctx) < 9000

    def test_uses_summary_when_set(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        doc = make_doc(1, long_text=True)
        doc.sections[0].summary = "My custom summary."
        ctx = engine._build_doc_context(doc)
        assert "My custom summary." in ctx

    def test_falls_back_to_text_when_no_summary(self):
        engine = IntelligenceEngine(provider=MockLLMProvider())
        doc = make_doc(1, long_text=True)
        doc.sections[0].summary = None
        ctx = engine._build_doc_context(doc)
        # Text first 100 chars used as fallback
        assert "word" in ctx


# ── _extract_json ─────────────────────────────────────────────────────────────

class TestExtractJson:
    def test_extracts_json_object(self):
        assert json.loads(_extract_json('{"key": "value"}')) == {"key": "value"}

    def test_extracts_json_array(self):
        assert json.loads(_extract_json('["a", "b", "c"]')) == ["a", "b", "c"]

    def test_extracts_from_json_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        assert json.loads(_extract_json(text)) == {"key": "value"}

    def test_extracts_from_plain_code_block(self):
        text = '```\n{"key": "value"}\n```'
        assert json.loads(_extract_json(text)) == {"key": "value"}

    def test_extracts_from_text_with_preamble(self):
        text = 'Here is the JSON result: {"a": 1, "b": 2}'
        assert json.loads(_extract_json(text)) == {"a": 1, "b": 2}

    def test_returns_stripped_text_if_no_json(self):
        text = "   no json here at all   "
        result = _extract_json(text)
        assert result == "no json here at all"

    def test_array_in_code_block(self):
        text = '```json\n["alpha", "beta"]\n```'
        assert json.loads(_extract_json(text)) == ["alpha", "beta"]

    def test_nested_json_object(self):
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = json.loads(_extract_json(text))
        assert result["outer"]["inner"] == [1, 2, 3]
