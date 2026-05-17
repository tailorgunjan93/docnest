"""Tests for IntelligenceEngine (LLM enrichment stages).

Phase: 3  |  Run: pytest tests/test_intelligence.py -v
LLM calls are mocked in unit tests — integration tests require Ollama.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestIntelligenceEngine:
    """TODO (Phase 3): Uncomment after IntelligenceEngine is implemented."""

    # def test_enrich_sections_fills_summary(self):
    #     from DOCNEST.intelligence import IntelligenceEngine
    #     engine = IntelligenceEngine(provider="ollama", model="llama3.2")
    #     doc = make_test_document()
    #     with patch.object(engine, "_call_llm", return_value="One sentence summary."):
    #         enriched = engine.enrich_sections(doc)
    #     assert all(s.summary for s in enriched.sections)

    # def test_enrich_document_fills_insights(self):
    #     from DOCNEST.intelligence import IntelligenceEngine
    #     engine = IntelligenceEngine()
    #     doc = make_test_document_with_summaries()
    #     mock_response = '''{"summary": "Test.", "insights": ["Insight 1"], "key_numbers": []}'''
    #     with patch.object(engine, "_call_llm", return_value=mock_response):
    #         enriched = engine.enrich_document(doc)
    #     assert len(enriched.insights) > 0

    pass
