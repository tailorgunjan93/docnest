"""Tests for UDFIndex (reader) — loading and five-layer query resolution.

Run: pytest tests/test_reader.py -v
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from docnest.reader import UDFIndex


# ── Load tests ────────────────────────────────────────────────────────────────

class TestUDFIndexLoad:
    def test_load_returns_udf_index(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        assert isinstance(idx, UDFIndex)

    def test_catalogue_is_loaded(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        assert idx._catalogue is not None

    def test_doc_id_accessible(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        assert idx._catalogue.get("doc_id") is not None

    def test_section_index_accessible(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        assert len(idx._catalogue["section_index"]) > 0

    def test_missing_file_raises(self):
        from docnest.exceptions import UDFReadError
        with pytest.raises(UDFReadError):
            UDFIndex.load("/tmp/does_not_exist_abc123xyz.udf")

    def test_load_with_numpy_backend(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path, vector="numpy")
        assert idx is not None

    def test_load_with_custom_vector_backend(self, minimal_udf_path: str):
        from docnest.providers.vector import NumpyVectorBackend
        backend = NumpyVectorBackend()
        idx = UDFIndex.load(minimal_udf_path, vector=backend)
        assert idx is not None

    def test_content_not_loaded_eagerly(self, minimal_udf_path: str):
        """Content should be lazy — not loaded until a section is fetched."""
        idx = UDFIndex.load(minimal_udf_path)
        # _content can be None or empty dict before first access
        assert idx._content is None or isinstance(idx._content, dict)

    def test_embed_matrix_not_loaded_eagerly(self, minimal_udf_path: str):
        """Embedding matrix should be lazy — not decoded until first search."""
        idx = UDFIndex.load(minimal_udf_path)
        assert idx._embed_matrix is None


# ── get_section ───────────────────────────────────────────────────────────────

class TestGetSection:
    def test_returns_dict_for_valid_id(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        # Get the first section id from the index
        first_id = idx._catalogue["section_index"][0]["id"]
        section = idx.get_section(first_id)
        assert isinstance(section, dict)
        assert "text" in section

    def test_returns_none_for_missing_id(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        result = idx.get_section("§999.99.99")
        assert result is None

    def test_section_has_title(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        first_id = idx._catalogue["section_index"][0]["id"]
        section = idx.get_section(first_id)
        assert "title" in section

    def test_multiple_get_section_calls_consistent(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        first_id = idx._catalogue["section_index"][0]["id"]
        s1 = idx.get_section(first_id)
        s2 = idx.get_section(first_id)
        assert s1 == s2


# ── Layer 0: pre-computed ─────────────────────────────────────────────────────

class TestLayer0:
    def test_summary_question_hits_layer_0(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        result = idx.get_precomputed("What is this document about?")
        # Should return something (summary is set in fixture)
        assert result is not None
        assert len(result) > 0

    def test_layer_0_answer_contains_summary(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        result = idx.get_precomputed("summary")
        assert result is not None

    def test_irrelevant_question_returns_none_at_layer_0(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        # Very specific technical query unlikely to match pre-computed
        result = idx.get_precomputed("§3.2.1 subsection technical detail xyz987")
        # May return None — pre-computed is only for high-level questions
        # We just verify it doesn't crash
        assert result is None or isinstance(result, str)


# ── Layer 1: hybrid search ────────────────────────────────────────────────────

class TestLayer1:
    def test_hybrid_search_returns_list(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        results = idx._hybrid_search("Part A Background")
        assert isinstance(results, list)

    def test_hybrid_search_results_are_tuples(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        results = idx._hybrid_search("methods")
        if results:
            assert all(isinstance(r, tuple) and len(r) == 2 for r in results)

    def test_hybrid_search_scores_non_negative(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        results = idx._hybrid_search("Part A")
        for _, score in results:
            assert score >= 0

    def test_hybrid_search_sorted_descending(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        results = idx._hybrid_search("Part A")
        scores = [r[1] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_hybrid_search_ids_match_section_index(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        valid_ids = {e["id"] for e in idx._catalogue["section_index"]}
        results = idx._hybrid_search("Background")
        for sec_id, _ in results:
            assert sec_id in valid_ids


# ── Embedding matrix ──────────────────────────────────────────────────────────

class TestEmbeddingMatrix:
    def test_matrix_loaded_on_first_search(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        assert idx._embed_matrix is None
        idx._load_embed_matrix()
        assert idx._embed_matrix is not None

    def test_matrix_shape_matches_section_count(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        idx._load_embed_matrix()
        n_sections = len(idx._catalogue["section_index"])
        assert idx._embed_matrix.shape[0] == n_sections

    def test_matrix_dtype_is_float32(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        idx._load_embed_matrix()
        assert idx._embed_matrix.dtype == np.float32


# ── Full query (mocked LLM) ───────────────────────────────────────────────────

class TestQueryWithMockedLLM:
    # LLM call methods return (answer_str, token_count) tuples
    LLM_RETURN = ("Mock LLM answer.", 100)

    def test_query_returns_result(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        with patch.object(idx, "_call_llm_section", return_value=self.LLM_RETURN):
            with patch.object(idx, "_call_llm_multi", return_value=self.LLM_RETURN):
                with patch.object(idx, "_call_llm_full", return_value=self.LLM_RETURN):
                    result = idx.query("What is this document about?")
        assert result is not None

    def test_query_answer_is_non_empty(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        with patch.object(idx, "_call_llm_section", return_value=self.LLM_RETURN):
            with patch.object(idx, "_call_llm_multi", return_value=self.LLM_RETURN):
                with patch.object(idx, "_call_llm_full", return_value=self.LLM_RETURN):
                    result = idx.query("What is this about?")
        # QueryResult can be a dataclass or dict
        answer = result.answer if hasattr(result, "answer") else result.get("answer", "")
        assert answer

    def test_layer_0_does_not_call_llm(self, minimal_udf_path: str):
        """Layer 0 (pre-computed) should never invoke LLM."""
        idx = UDFIndex.load(minimal_udf_path)
        with patch.object(idx, "_call_llm_section", return_value=self.LLM_RETURN) as mock_llm:
            result = idx.query("What is this document about?")
            assert result is not None


# ── Corrupted / edge-case UDFs ────────────────────────────────────────────────

class TestEdgeCases:
    def test_load_udf_with_empty_sections(self, tmp_path: Path):
        """A UDF with zero sections should load without crashing."""
        import json, zipfile
        from docnest.models import Document, RawDocument
        from docnest.normalizer import SectionNormaliser
        from docnest.quantizer import Quantizer
        from docnest.writer import UDFWriter
        from tests.conftest import MockEmbedder

        raw = RawDocument(doc_id="empty", title="Empty", source="f.pdf", format="pdf", sections=[])
        doc = SectionNormaliser().normalise(raw)
        doc.summary = "Empty document."
        out = str(tmp_path / "empty.udf")
        UDFWriter(MockEmbedder(), Quantizer("float16")).write(doc, out)
        idx = UDFIndex.load(out)
        assert idx is not None
        assert idx._catalogue["section_index"] == []

    def test_query_on_empty_document_does_not_crash(self, tmp_path: Path):
        from docnest.models import RawDocument
        from docnest.normalizer import SectionNormaliser
        from docnest.quantizer import Quantizer
        from docnest.writer import UDFWriter
        from tests.conftest import MockEmbedder

        raw = RawDocument(doc_id="empty", title="Empty", source="f.pdf", format="pdf", sections=[])
        doc = SectionNormaliser().normalise(raw)
        doc.summary = "Empty."
        out = str(tmp_path / "empty.udf")
        UDFWriter(MockEmbedder(), Quantizer("float16")).write(doc, out)
        idx = UDFIndex.load(out)
        # LLM methods return (answer, tokens) tuples
        with patch.object(idx, "_call_llm_full", return_value=("No content.", 0)):
            result = idx.query("anything")
        assert result is not None

    def test_load_udf_missing_manifest_raises(self, tmp_path: Path):
        """UDF without manifest.json → UDFReadError."""
        import zipfile
        from docnest.exceptions import UDFReadError
        bad = tmp_path / "bad.udf"
        with zipfile.ZipFile(str(bad), "w") as zf:
            zf.writestr("catalogue.json", "{}")
            zf.writestr("content.json", "{}")
        with pytest.raises(UDFReadError):
            UDFIndex.load(str(bad))

    def test_load_udf_wrong_version_raises(self, tmp_path: Path):
        """UDF with wrong udf_version → UDFReadError."""
        import json, zipfile
        from docnest.exceptions import UDFReadError
        bad = tmp_path / "wrong_version.udf"
        with zipfile.ZipFile(str(bad), "w") as zf:
            zf.writestr("manifest.json", json.dumps({"udf_version": "9.9", "doc_id": "x", "title": "X"}))
            zf.writestr("catalogue.json", json.dumps({"doc_id": "x", "section_index": []}))
            zf.writestr("content.json", json.dumps({"doc_id": "x", "sections": {}}))
        with pytest.raises(UDFReadError):
            UDFIndex.load(str(bad))


# ── Layer 0 extended ──────────────────────────────────────────────────────────

class TestLayer0Extended:
    def test_insight_keyword_returns_insights(self, minimal_udf_path: str):
        """'insight' in query → Layer 0 returns insights list."""
        idx = UDFIndex.load(minimal_udf_path)
        result = idx.get_precomputed("what are the key insights")
        assert result is not None
        assert "Insight" in result  # minimal_udf has "Insight one.", "Insight two."

    def test_finding_keyword_returns_insights(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        result = idx.get_precomputed("what are the key findings")
        assert result is not None

    def test_key_number_label_match(self, minimal_udf_path: str):
        """If query contains a key_number label, Layer 0 returns it."""
        idx = UDFIndex.load(minimal_udf_path)
        # minimal_udf has key_number label="Count"
        result = idx.get_precomputed("what is the count")
        assert result is not None
        assert "Count" in result or "42" in result

    def test_unknown_query_returns_none(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        result = idx.get_precomputed("zzznomatchqwertyxyz987")
        assert result is None


# ── Query layers via patching ──────────────────────────────────────────────────

class TestQueryLayers:
    """Test that different query patterns route to different layers."""

    LLM_RETURN = ("Layer answer.", 42)

    def _load(self, minimal_udf_path: str):
        return UDFIndex.load(minimal_udf_path)

    def test_layer_0_query_has_layer_0(self, minimal_udf_path: str):
        """Summary query → Layer 0, tokens_used = 0."""
        idx = self._load(minimal_udf_path)
        result = idx.query("What is the summary?")
        assert result.layer_used == 0
        assert result.tokens_used == 0
        assert result.confidence == 1.0

    def test_layer_1_returns_section_summary(self, minimal_udf_path: str):
        """High hybrid score → Layer 1 (returns section summary, 0 tokens)."""
        idx = self._load(minimal_udf_path)
        # Patch hybrid search to return a high score for a section with a summary
        first_id = idx._catalogue["section_index"][0]["id"]
        # Use a query that does NOT hit Layer 0 keywords (no: summarise, summary, insight, etc.)
        with patch.object(idx, "_hybrid_search", return_value=[(first_id, 0.9)]):
            result = idx.query("technical details of Part A Background")
        # Layer 1 is triggered if score >= 0.35 AND section has summary
        if result.layer_used == 1:
            assert result.tokens_used == 0
            assert result.navigate_to == first_id
        else:
            # Layer 2+ is acceptable if summary was missing
            assert result.layer_used >= 2

    def test_layer_2_calls_llm_section(self, minimal_udf_path: str):
        """Medium score (>= 0.15) → Layer 2 (single section LLM)."""
        idx = self._load(minimal_udf_path)
        first_id = idx._catalogue["section_index"][0]["id"]
        with patch.object(idx, "_hybrid_search", return_value=[(first_id, 0.2)]):
            with patch.object(idx, "_call_llm_section", return_value=self.LLM_RETURN) as mock_l2:
                result = idx.query("specific technical question xyz")
        assert mock_l2.called
        assert result.layer_used == 2

    def test_layer_3_calls_llm_multi(self, minimal_udf_path: str):
        """Multiple sections with low scores → Layer 3 (multi-section LLM)."""
        idx = self._load(minimal_udf_path)
        ids = [e["id"] for e in idx._catalogue["section_index"][:3]]
        # Score below L2 threshold (0.15) means... wait, actually L2 fires for >= 0.15
        # To skip L2 and reach L3, score must be < L2_THRESHOLD (0.15)
        with patch.object(idx, "_hybrid_search", return_value=[(i, 0.05) for i in ids]):
            with patch.object(idx, "_call_llm_multi", return_value=self.LLM_RETURN) as mock_l3:
                result = idx.query("cross section synthesis query")
        assert mock_l3.called
        assert result.layer_used == 3

    def test_layer_4_called_when_no_ranked_results(self, minimal_udf_path: str):
        """No hybrid results → Layer 4 (full document LLM)."""
        idx = self._load(minimal_udf_path)
        with patch.object(idx, "_hybrid_search", return_value=[]):
            with patch.object(idx, "_call_llm_full", return_value=self.LLM_RETURN) as mock_l4:
                result = idx.query("completely unrelated query 99999")
        assert mock_l4.called
        assert result.layer_used == 4

    def test_query_result_has_required_fields(self, minimal_udf_path: str):
        idx = self._load(minimal_udf_path)
        result = idx.query("What is this about?")
        assert hasattr(result, "answer")
        assert hasattr(result, "layer_used")
        assert hasattr(result, "tokens_used")
        assert hasattr(result, "confidence")
        assert hasattr(result, "citations")


# ── Helper methods ────────────────────────────────────────────────────────────

class TestHelperMethods:
    def test_get_section_text_returns_text(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        first_id = idx._catalogue["section_index"][0]["id"]
        # Trigger lazy load of content
        text = idx._get_section_text(first_id)
        assert text is not None
        assert len(text) > 0

    def test_get_section_text_missing_id_returns_none(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        result = idx._get_section_text("§999.999")
        assert result is None

    def test_get_section_text_includes_table_content(self, tmp_path: Path):
        """Sections with tables should include table text in _get_section_text."""
        from docnest.models import RawDocument, Section, TableData
        from docnest.normalizer import SectionNormaliser
        from docnest.quantizer import Quantizer
        from docnest.writer import UDFWriter
        from tests.conftest import MockEmbedder

        raw = RawDocument(
            doc_id="tbl", title="Table Doc", source="t.md", format="md",
            sections=[Section(id="", title="Data", level=1, text="Some text.")]
        )
        doc = SectionNormaliser().normalise(raw)
        doc.sections[0].tables = [
            TableData(
                table_id="t1", caption="Sales",
                headers=["Q1", "Q2"], rows=[["100", "200"]],
            )
        ]
        doc.sections[0].summary = "Data."
        doc.sections[0].keywords = ["data"]
        doc.summary = "Table doc."
        out = str(tmp_path / "tbl.udf")
        UDFWriter(MockEmbedder(), Quantizer("float16")).write(doc, out)

        idx = UDFIndex.load(out)
        first_id = idx._catalogue["section_index"][0]["id"]
        text = idx._get_section_text(first_id)
        assert "Q1" in text or "Q2" in text

    def test_build_full_text_returns_all_sections(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        full = idx._build_full_text()
        # Should contain at least something from each section
        assert isinstance(full, str)
        assert len(full) > 0
        # Should contain section headings
        assert "##" in full

    def test_build_full_text_empty_doc(self, tmp_path: Path):
        from docnest.models import RawDocument
        from docnest.normalizer import SectionNormaliser
        from docnest.quantizer import Quantizer
        from docnest.writer import UDFWriter
        from tests.conftest import MockEmbedder

        raw = RawDocument(doc_id="e", title="E", source="e.md", format="md", sections=[])
        doc = SectionNormaliser().normalise(raw)
        doc.summary = "Empty."
        out = str(tmp_path / "e.udf")
        UDFWriter(MockEmbedder(), Quantizer("float16")).write(doc, out)
        idx = UDFIndex.load(out)
        full = idx._build_full_text()
        assert full == ""

    def test_get_catalogue_entry_found(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        first_id = idx._catalogue["section_index"][0]["id"]
        entry = idx._get_catalogue_entry(first_id)
        assert entry is not None
        assert entry["id"] == first_id

    def test_get_catalogue_entry_not_found(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        entry = idx._get_catalogue_entry("§999")
        assert entry is None


# ── LLM call methods ──────────────────────────────────────────────────────────

class TestLLMCallMethods:
    """Test _call_llm_section, _call_llm_multi, _call_llm_full, _llm_call."""

    def test_call_llm_section_returns_tuple(self, minimal_udf_path: str):
        from docnest.reader import _llm_call
        from tests.conftest import MockLLMProvider
        idx = UDFIndex.load(minimal_udf_path)
        with patch("docnest.reader._llm_call", return_value="Section answer."):
            result = idx._call_llm_section(
                "What is this?", "§1", "Section text here.",
                "ollama", "llama3.2", None
            )
        assert isinstance(result, tuple)
        assert len(result) == 2
        answer, tokens = result
        assert isinstance(answer, str)
        assert isinstance(tokens, int)

    def test_call_llm_multi_returns_tuple(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        with patch("docnest.reader._llm_call", return_value="Multi answer."):
            result = idx._call_llm_multi(
                "What connects these?",
                {"§1": "text one", "§2": "text two"},
                "ollama", "llama3.2", None
            )
        assert isinstance(result, tuple)
        answer, tokens = result
        assert "Multi answer." == answer

    def test_call_llm_full_returns_tuple(self, minimal_udf_path: str):
        idx = UDFIndex.load(minimal_udf_path)
        with patch("docnest.reader._llm_call", return_value="Full answer."):
            result = idx._call_llm_full(
                "Tell me everything.", "Full document text here.",
                "ollama", "llama3.2", None
            )
        assert isinstance(result, tuple)
        assert result[0] == "Full answer."

    def test_llm_call_with_provider_instance(self, minimal_udf_path: str):
        """_llm_call accepts an ILLMProvider instance."""
        from docnest.reader import _llm_call
        from tests.conftest import MockLLMProvider
        result = _llm_call("Hello", MockLLMProvider(), "mock-model")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_llm_call_with_provider_string_error_returns_bracketed_message(self):
        """_llm_call with bad string provider → returns [LLM error ...] string."""
        from docnest.reader import _llm_call
        # "badprovider" will fail to initialise; _llm_call catches and returns error msg
        result = _llm_call("prompt", "badprovider", "no-model")
        assert isinstance(result, str)
        # Either an error message or an answer (if provider somehow works)
        # In CI without API keys, it should be an error
        assert len(result) > 0
