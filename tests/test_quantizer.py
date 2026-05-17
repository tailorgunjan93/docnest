"""Tests for the Quantizer — embedding compression and decompression.

Phase: 2  |  Issue: #3  |  Run: pytest tests/test_quantizer.py -v
These tests have complete implementations — ready to run once Quantizer is built.
"""
import pytest
import numpy as np
from docforge.quantizer import Quantizer
from docforge.exceptions import QuantizationError


class TestQuantizer:
    """TODO (Phase 2): Uncomment all tests after Quantizer is implemented."""

    # def test_float16_roundtrip_within_tolerance(self):
    #     q = Quantizer("float16")
    #     vec = np.random.randn(768).astype(np.float32)
    #     assert np.allclose(vec, q.dequantize(q.quantize(vec), 768), atol=0.01)

    # def test_int8_roundtrip_within_tolerance(self):
    #     q = Quantizer("int8")
    #     vec = np.random.randn(768).astype(np.float32)
    #     assert np.allclose(vec, q.dequantize(q.quantize(vec), 768), atol=0.02)

    # def test_binary_size_reduction(self):
    #     q = Quantizer("binary")
    #     vec = np.random.randn(1536).astype(np.float32)
    #     assert len(q.quantize(vec)) == 192  # 1536 / 8

    # def test_float16_half_the_size_of_float32(self):
    #     f32 = Quantizer("float32").quantize(np.ones(768, dtype=np.float32))
    #     f16 = Quantizer("float16").quantize(np.ones(768, dtype=np.float32))
    #     assert len(f16) == len(f32) // 2

    # def test_invalid_mode_raises(self):
    #     with pytest.raises(ValueError, match="Unsupported mode"):
    #         Quantizer("bfloat16")

    pass
