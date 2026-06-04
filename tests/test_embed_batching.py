"""Large PDFs · Step 1b — bounded-batch embedding (test-first).

FAILS until docnest.embedder.embed_in_batches lands and UDFWriter uses it. Pins the
bounded-memory goal: embedding never processes more than batch_size texts at once, while
preserving order and result shape.

Run: pytest tests/test_embed_batching.py -v
"""
from __future__ import annotations

import numpy as np
import pytest

from docnest.embedder import IEmbedder


class _Recording(IEmbedder):
    """Records the largest batch it is ever asked to embed."""
    def __init__(self, dims: int = 8) -> None:
        self._dims = dims
        self.max_batch = 0
        self.calls = 0

    def embed(self, texts):
        self.max_batch = max(self.max_batch, len(texts))
        self.calls += 1
        return np.ones((len(texts), self._dims), dtype=np.float32)

    @property
    def dims(self) -> int:
        return self._dims

    @property
    def model_name(self) -> str:
        return "recording"


class TestEmbedInBatches:
    def test_never_exceeds_batch_size(self):
        from docnest.embedder import embed_in_batches
        e = _Recording()
        out = embed_in_batches(e, [f"t{i}" for i in range(200)], batch_size=64)
        assert out.shape == (200, 8)
        assert e.max_batch <= 64
        assert e.calls == 4                       # ceil(200 / 64)

    def test_empty_input(self):
        from docnest.embedder import embed_in_batches
        e = _Recording()
        out = embed_in_batches(e, [], batch_size=64)
        assert out.shape[0] == 0
        assert e.calls == 0

    def test_preserves_order(self):
        from docnest.embedder import embed_in_batches

        class _Idx(IEmbedder):
            def embed(self, texts):
                return np.array([[float(len(t))] for t in texts], dtype=np.float32)
            @property
            def dims(self): return 1
            @property
            def model_name(self): return "idx"

        texts = ["a", "bb", "ccc", "dddd", "eeeee"]
        out = embed_in_batches(_Idx(), texts, batch_size=2)
        assert [r[0] for r in out] == [1.0, 2.0, 3.0, 4.0, 5.0]


class TestWriterUsesBatching:
    def test_writer_embeds_in_bounded_batches(self, tmp_path):
        from docnest.writer import UDFWriter
        from docnest.models import Document, Section

        secs = [Section(id=f"§{i}", title=f"S{i}", level=1, text=f"body text {i}")
                for i in range(150)]
        doc = Document(doc_id="d", title="t", source="x", format="md", sections=secs)

        rec = _Recording()
        writer = UDFWriter(embedder=rec, embed_batch_size=32)
        writer.write(doc, str(tmp_path / "out.udf"))
        assert rec.max_batch <= 32                 # bounded, not all 150 at once
