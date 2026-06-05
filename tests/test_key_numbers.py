"""Deterministic intelligence — key-number extraction (test-first).

FAILS until docnest/key_numbers.py lands. Populates Section/Document key_numbers WITHOUT an
LLM so Layer 0 (0-token) can answer numeric lookups (revives the Observer's-Tax 0-token path).

Run: pytest tests/test_key_numbers.py -v
"""
from __future__ import annotations

import pytest

from docnest.models import Document, Section


_METRICS = ("- **Uptime:** 99.97% (SLA target: 99.9%)\n"
            "- **Avg response time:** 142ms (down from 310ms)\n"
            "- **Cost savings:** $4,050/month\n"
            "- **Services migrated:** 14 of 14")


class TestExtractKeyNumbers:
    def test_bullet_label_and_value(self):
        from docnest.key_numbers import extract_key_numbers
        kns = extract_key_numbers(_METRICS, section_id="§1.2.2")
        labels = {k.label.lower(): k for k in kns}
        assert "uptime" in labels
        # value carries the readable figure; canonical is parseable
        assert "99.97" in labels["uptime"].value
        assert any("cost savings" == k.label.lower() for k in kns)
        assert any(k.section == "§1.2.2" for k in kns)

    def test_currency_and_percent_parsed(self):
        from docnest.key_numbers import extract_key_numbers
        kns = {k.label.lower(): k.value for k in extract_key_numbers(_METRICS, "§x")}
        assert "4050" in kns.get("cost savings", "").replace(",", "")

    def test_filters_years_listmarkers_identifiers(self):
        from docnest.key_numbers import extract_key_numbers
        text = ("1. Launch portal\n2. Adopt tracing\n"
                "ISO 27001 audit passed. Completed AZ-204 in 2025.")
        vals = {k.value for k in extract_key_numbers(text, "§y")}
        # bare year, list ordinals, and identifier numbers must NOT appear as key numbers
        assert "2025" not in vals
        assert "27001" not in vals
        assert "204" not in vals

    def test_requires_a_label(self):
        from docnest.key_numbers import extract_key_numbers
        # a lone number with no bindable label is dropped (no "(value)" noise)
        kns = extract_key_numbers("Then 5 happened somewhere.", "§z")
        assert all(k.label.strip() for k in kns)


class TestDocumentEnrichment:
    def test_enrich_fills_doc_key_numbers(self):
        from docnest.key_numbers import enrich_key_numbers
        doc = Document(
            doc_id="d", title="t", source="x", format="md",
            sections=[Section(id="§1", title="Key Metrics", level=1, text=_METRICS)],
        )
        assert not doc.key_numbers
        enrich_key_numbers(doc)
        assert doc.key_numbers
        assert any(k.label.lower() == "uptime" for k in doc.key_numbers)

    def test_enrich_is_noop_when_already_populated(self):
        from docnest.key_numbers import enrich_key_numbers
        from docnest.models import KeyNumber
        doc = Document(doc_id="d", title="t", source="x", format="md",
                       sections=[Section(id="§1", title="S", level=1, text=_METRICS)],
                       key_numbers=[KeyNumber(label="existing", value="1", section="§1")])
        enrich_key_numbers(doc)
        assert [k.label for k in doc.key_numbers] == ["existing"]   # untouched


class TestDurationExtraction:
    def test_unit_attached_duration_is_extracted(self):
        from docnest.key_numbers import extract_key_numbers
        kns = {k.label.lower(): k.value for k in
               extract_key_numbers("- **Avg response time:** 142ms (down from 310ms)", "§x")}
        # the unit-attached number (142ms) must NOT be skipped as an identifier
        assert any("142" in v for v in kns.values())


class TestRobustMatching:
    """Layer-0 matching: word-order tolerant + modifier-tolerant, ambiguity-guarded."""

    def _idx(self, key_numbers):
        from docnest.reader import UDFIndex
        return UDFIndex(
            catalogue={"section_index": [], "summary": "", "insights": [],
                       "key_numbers": key_numbers},
            content={"sections": {}}, zip_path="dummy.udf", embedding_dims=0)

    def test_word_order_and_modifier_tolerant(self):
        idx = self._idx([{"label": "Avg response time", "value": "142ms", "section": "§1"}])
        # "avg" is an optional modifier; word order differs
        assert "142" in (idx.get_precomputed("what was the average response time?") or "")

    def test_ambiguous_values_are_skipped(self):
        idx = self._idx([
            {"label": "Monthly cloud spend", "value": "$18,400", "section": "§1"},
            {"label": "Monthly cloud spend", "value": "$14,350", "section": "§1"},
        ])
        # two different values under the same label → unsafe → no Layer-0 answer
        assert idx.get_precomputed("what is the monthly cloud spend?") is None


class TestLayer0Revived:
    """The payoff: deterministic key_numbers let the reader answer at Layer 0 (0 tokens)."""

    def test_reader_answers_numeric_lookup_at_layer_0(self):
        from docnest.reader import UDFIndex
        catalogue = {
            "section_index": [{"id": "§1.2.2", "title": "Key Metrics", "level": 1,
                               "keywords": ["uptime"]}],
            "summary": "", "insights": [],
            "key_numbers": [
                {"label": "Uptime", "value": "99.97%", "unit": "%", "section": "§1.2.2"},
                {"label": "Total engineers", "value": "24", "section": "§1.5.2"},
            ],
        }
        content = {"sections": {"§1.2.2": {"title": "Key Metrics", "level": 1,
                                           "text": _METRICS, "tables": []}}}
        idx = UDFIndex(catalogue=catalogue, content=content,
                       zip_path="dummy.udf", embedding_dims=0)
        res = idx.query("what was the platform uptime percentage?")
        assert res.layer_used == 0
        assert res.tokens_used == 0
        assert "99.97" in res.answer

    def test_allow_llm_false_answers_at_layer_0(self):
        from docnest.reader import UDFIndex
        catalogue = {"section_index": [], "summary": "", "insights": [],
                     "key_numbers": [{"label": "Uptime", "value": "99.97%",
                                      "unit": "%", "section": "§1"}]}
        idx = UDFIndex(catalogue=catalogue, content={"sections": {}},
                       zip_path="dummy.udf", embedding_dims=0)
        # deterministic-only: Layer-0 still answers (0 tokens)
        hit = idx.query("what is the uptime?", allow_llm=False)
        assert hit.layer_used == 0 and hit.tokens_used == 0 and "99.97" in hit.answer
        # a non-precomputed query returns no deterministic answer (never calls an LLM)
        miss = idx.query("explain the geopolitical implications", allow_llm=False)
        assert miss.layer_used == -1 and miss.tokens_used == 0
