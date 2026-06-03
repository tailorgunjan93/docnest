"""Task 4 · Step 1 — budgeted table rendering in the production query path.

Test-first (Phase 3): FAILS until reader._render_table / _section_parts land and the
5-row cap + prose-cap-chopping are removed.

Run: pytest tests/test_table_rendering.py -v
"""
from __future__ import annotations

import pytest

from docnest.providers.llm import ILLMProvider


# ── Helpers ─────────────────────────────────────────────────────────────────

class RecordingLLM(ILLMProvider):
    """Captures the prompt it's given; returns a fixed answer (no network)."""
    def __init__(self) -> None:
        self.prompt = ""

    def complete(self, prompt: str, system: str = "", temperature: float = 0.1,
                 max_tokens: int = 512) -> str:
        self.prompt = prompt
        return "ok"

    @property
    def provider_name(self) -> str:
        return "rec"

    @property
    def model_name(self) -> str:
        return "rec"


def _table(rows, headers=("A", "B")):
    return {"table_id": "t1", "caption": None, "headers": list(headers), "rows": rows}


def _index_with(section_text: str, rows):
    """Build a minimal in-memory UDFIndex with one section + one table."""
    from docnest.reader import UDFIndex
    catalogue = {
        "section_index": [{"id": "§1", "title": "Data", "level": 1, "keywords": ["data"]}],
        "summary": "", "insights": [], "key_numbers": [],
    }
    content = {"sections": {"§1": {"title": "Data", "level": 1,
                                   "text": section_text, "tables": [_table(rows)]}}}
    # embedding_dims=0 → no embeddings needed; dummy zip path (storage probe fails gracefully)
    return UDFIndex(catalogue=catalogue, content=content, zip_path="dummy.udf",
                    embedding_dims=0)


# ── Unit: _render_table (pure) ──────────────────────────────────────────────

class TestRenderTable:
    def test_small_table_renders_all_rows_no_note(self):
        from docnest.reader import _render_table
        out = _render_table(_table([["1", "2"], ["3", "4"]]))
        assert "1 | 2" in out and "3 | 4" in out
        assert "more rows" not in out

    def test_large_table_caps_and_notes_omitted(self):
        from docnest.reader import _render_table
        rows = [[f"row{i}value", f"{i}"] for i in range(100)]
        out = _render_table(_table(rows), budget=200)
        assert "more rows" in out
        # at least the first row shown, and far from all 100 rendered
        assert "row0value" in out and "row99value" not in out

    def test_empty_rows_just_headers(self):
        from docnest.reader import _render_table
        out = _render_table(_table([]))
        assert "A | B" in out and "more rows" not in out


# ── Integration: _get_section_text no longer caps at 5 rows ─────────────────

class TestSectionTextRows:
    def test_rows_beyond_five_are_included(self):
        rows = [[f"r{i}", str(i)] for i in range(8)]
        idx = _index_with("Prose.", rows)
        txt = idx._get_section_text("§1")
        assert "r5" in txt and "r6" in txt and "r7" in txt   # was capped at 5


# ── Layer-2: table survives the prose char cap ──────────────────────────────

class TestLayer2TableSurvivesProseCap:
    def test_table_row_present_after_long_prose(self):
        long_prose = "x " * 2000          # >2000 chars of prose
        rows = [["UNIQUE_LATE_ROW", "999"]]
        idx = _index_with(long_prose, rows)
        rec = RecordingLLM()
        idx._call_llm_section("what is the value?", "§1",
                              idx._get_section_text("§1"), rec)
        assert "UNIQUE_LATE_ROW" in rec.prompt   # table not chopped by the prose cap
