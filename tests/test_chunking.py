"""Large PDFs · Step 1a — passage chunking (test-first).

FAILS until docnest/chunking.py lands. Pins ADR-0007 / the task docs: deterministic,
boundary-aware, bounded-size passages with best-effort overlap; tiny text → 1 passage.

Run: pytest tests/test_chunking.py -v
"""
from __future__ import annotations

import re

import pytest


class TestChunkText:
    def test_short_text_single_passage(self):
        from docnest.chunking import chunk_text
        assert chunk_text("a short section.", max_chars=2000) == ["a short section."]

    def test_empty_text_no_passages(self):
        from docnest.chunking import chunk_text
        assert chunk_text("", max_chars=2000) == []
        assert chunk_text("   \n  ", max_chars=2000) == []

    def test_long_text_splits_into_bounded_passages(self):
        from docnest.chunking import chunk_text
        para = ("Sentence number {i} with enough words to take up space. ")
        text = "\n\n".join("".join(para.format(i=j) for _ in range(8)) for j in range(40))
        passages = chunk_text(text, max_chars=500, overlap=50)
        assert len(passages) > 1
        assert all(len(p) <= 500 for p in passages)          # hard cap honoured

    def test_no_content_lost(self):
        from docnest.chunking import chunk_text
        text = "\n\n".join(f"Paragraph {j}: " + "word " * 60 for j in range(20))
        passages = chunk_text(text, max_chars=400, overlap=40)
        # every alphanumeric token of the source appears in some passage
        src_tokens = set(re.findall(r"\w+", text))
        seen = set()
        for p in passages:
            seen |= set(re.findall(r"\w+", p))
        assert src_tokens <= seen

    def test_overlap_between_consecutive_passages(self):
        from docnest.chunking import chunk_text
        text = " ".join(f"token{i}" for i in range(400))   # one long line
        passages = chunk_text(text, max_chars=300, overlap=60)
        assert len(passages) > 1
        # at least one adjacent pair shares a token (best-effort overlap)
        shared = False
        for a, b in zip(passages, passages[1:]):
            if set(re.findall(r"\w+", a)) & set(re.findall(r"\w+", b)):
                shared = True
                break
        assert shared

    def test_hard_split_when_single_unit_exceeds_max(self):
        from docnest.chunking import chunk_text
        text = "x" * 5000                                    # no boundaries at all
        passages = chunk_text(text, max_chars=1000, overlap=0)
        assert len(passages) >= 5
        assert all(len(p) <= 1000 for p in passages)

    def test_deterministic(self):
        from docnest.chunking import chunk_text
        text = "\n\n".join(f"Para {j} " + "lorem ipsum " * 30 for j in range(15))
        assert chunk_text(text, max_chars=500, overlap=50) == \
               chunk_text(text, max_chars=500, overlap=50)
