"""Tests for embedding providers.

Phase: 2  |  Run: pytest tests/test_embedder.py -v
"""
import pytest
import numpy as np
from docforge.embedder import NomicEmbedder, OpenAIEmbedder


class TestNomicEmbedder:
    """TODO (Phase 2): Uncomment after NomicEmbedder is implemented."""

    # @pytest.mark.integration  # requires fastembed installed + model downloaded
    # def test_embed_returns_correct_shape(self):
    #     embedder = NomicEmbedder()
    #     vectors = embedder.embed(["Hello world", "This is a test"])
    #     assert vectors.shape == (2, 768)
    #     assert vectors.dtype == np.float32

    # def test_dims_property(self):
    #     assert NomicEmbedder().dims == 768

    pass
