"""Tests for the Quantizer — embedding compression and decompression.

Run: pytest tests/test_quantizer.py -v
"""
from __future__ import annotations

import pytest
import numpy as np

from docnest.quantizer import Quantizer


RNG = np.random.default_rng(0)


def rand_vec(dims: int = 768) -> np.ndarray:
    return RNG.standard_normal(dims).astype(np.float32)


# ── Construction ──────────────────────────────────────────────────────────────

class TestQuantizerConstruction:
    def test_default_mode_is_float16(self):
        q = Quantizer()
        assert q.mode == "float16"

    def test_valid_modes_accepted(self):
        for mode in ("float32", "float16", "int8", "binary"):
            q = Quantizer(mode)
            assert q.mode == mode

    def test_invalid_mode_raises(self):
        with pytest.raises((ValueError, AssertionError)):
            Quantizer("bfloat16")


# ── float32 ───────────────────────────────────────────────────────────────────

class TestFloat32:
    def test_roundtrip_exact(self):
        q = Quantizer("float32")
        vec = rand_vec()
        out = q.dequantize(q.quantize(vec), len(vec))
        np.testing.assert_array_equal(vec, out)

    def test_output_size_is_4_bytes_per_dim(self):
        q = Quantizer("float32")
        assert len(q.quantize(rand_vec(768))) == 768 * 4

    def test_stride_equals_4_times_dims(self):
        q = Quantizer("float32")
        assert q.stride(768) == 768 * 4


# ── float16 ───────────────────────────────────────────────────────────────────

class TestFloat16:
    def test_roundtrip_within_tolerance(self):
        q = Quantizer("float16")
        vec = rand_vec()
        out = q.dequantize(q.quantize(vec), len(vec))
        np.testing.assert_allclose(vec, out, atol=0.01)

    def test_output_size_half_of_float32(self):
        vec = rand_vec(768)
        f32 = Quantizer("float32").quantize(vec)
        f16 = Quantizer("float16").quantize(vec)
        assert len(f16) == len(f32) // 2

    def test_output_size_is_2_bytes_per_dim(self):
        q = Quantizer("float16")
        assert len(q.quantize(rand_vec(768))) == 768 * 2

    def test_stride_equals_2_times_dims(self):
        q = Quantizer("float16")
        assert q.stride(768) == 768 * 2

    def test_different_vectors_give_different_bytes(self):
        q = Quantizer("float16")
        b1 = q.quantize(np.ones(64, dtype=np.float32))
        b2 = q.quantize(-np.ones(64, dtype=np.float32))
        assert b1 != b2


# ── int8 ──────────────────────────────────────────────────────────────────────

class TestInt8:
    def test_roundtrip_preserves_direction(self):
        """int8 dequantize preserves direction (cosine sim ≈ 1) but not magnitude."""
        q = Quantizer("int8")
        vec = rand_vec()
        out = q.dequantize(q.quantize(vec), len(vec))
        # Normalise both and check cosine similarity
        v_norm = vec / (np.linalg.norm(vec) + 1e-8)
        o_norm = out / (np.linalg.norm(out) + 1e-8)
        cosine = float(np.dot(v_norm, o_norm))
        assert cosine > 0.99, f"Direction not preserved: cosine={cosine:.4f}"

    def test_output_size_is_1_byte_per_dim(self):
        q = Quantizer("int8")
        assert len(q.quantize(rand_vec(768))) == 768

    def test_stride_equals_dims(self):
        q = Quantizer("int8")
        assert q.stride(768) == 768

    def test_near_zero_vector_roundtrip(self):
        q = Quantizer("int8")
        vec = np.zeros(128, dtype=np.float32)
        out = q.dequantize(q.quantize(vec), 128)
        np.testing.assert_allclose(vec, out, atol=0.02)


# ── binary ────────────────────────────────────────────────────────────────────

class TestBinary:
    def test_output_size_1536_dims(self):
        q = Quantizer("binary")
        assert len(q.quantize(rand_vec(1536))) == 192  # 1536 / 8

    def test_output_size_768_dims(self):
        q = Quantizer("binary")
        assert len(q.quantize(rand_vec(768))) == 96  # 768 / 8

    def test_output_size_padded_for_non_multiple_of_8(self):
        import math
        q = Quantizer("binary")
        dims = 100
        expected = math.ceil(dims / 8)
        assert len(q.quantize(rand_vec(dims))) == expected

    def test_stride_correct(self):
        import math
        q = Quantizer("binary")
        assert q.stride(1536) == 192
        assert q.stride(768) == 96

    def test_positive_values_give_mostly_ones(self):
        q = Quantizer("binary")
        vec = np.ones(8, dtype=np.float32)  # all positive → all 1 bits
        data = q.quantize(vec)
        assert data == b"\xff"

    def test_negative_values_give_mostly_zeros(self):
        q = Quantizer("binary")
        vec = -np.ones(8, dtype=np.float32)  # all negative → all 0 bits
        data = q.quantize(vec)
        assert data == b"\x00"

    def test_32x_size_reduction_vs_float32(self):
        vec = rand_vec(1536)
        f32_size = len(Quantizer("float32").quantize(vec))
        bin_size = len(Quantizer("binary").quantize(vec))
        assert f32_size / bin_size == pytest.approx(32, abs=1)


# ── Batch consistency ─────────────────────────────────────────────────────────

class TestBatchConsistency:
    @pytest.mark.parametrize("mode", ["float32", "float16", "int8"])
    def test_two_vectors_independent(self, mode: str):
        """Quantizing v1 then v2 must give same result as quantizing each alone."""
        q = Quantizer(mode)
        v1, v2 = rand_vec(64), rand_vec(64)
        b1_solo = q.quantize(v1)
        b2_solo = q.quantize(v2)
        assert b1_solo == q.quantize(v1)
        assert b2_solo == q.quantize(v2)

    @pytest.mark.parametrize("dims", [64, 256, 384, 768, 1024, 1536])
    def test_float16_roundtrip_various_dims(self, dims: int):
        q = Quantizer("float16")
        vec = rand_vec(dims)
        out = q.dequantize(q.quantize(vec), dims)
        np.testing.assert_allclose(vec, out, atol=0.01)


# ── cosine_similarity ─────────────────────────────────────────────────────────

class TestCosineSimilarity:
    def test_identical_vectors_score_1(self):
        v = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        assert Quantizer.cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)

    def test_opposite_vectors_score_minus_1(self):
        v = np.array([1.0, 0.0], dtype=np.float32)
        w = np.array([-1.0, 0.0], dtype=np.float32)
        assert Quantizer.cosine_similarity(v, w) == pytest.approx(-1.0, abs=1e-6)

    def test_orthogonal_vectors_score_0(self):
        v = np.array([1.0, 0.0], dtype=np.float32)
        w = np.array([0.0, 1.0], dtype=np.float32)
        assert Quantizer.cosine_similarity(v, w) == pytest.approx(0.0, abs=1e-6)

    def test_zero_vector_returns_0(self):
        zero = np.zeros(4, dtype=np.float32)
        v = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        assert Quantizer.cosine_similarity(zero, v) == 0.0
        assert Quantizer.cosine_similarity(v, zero) == 0.0

    def test_returns_float(self):
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        w = np.array([4.0, 5.0, 6.0], dtype=np.float32)
        result = Quantizer.cosine_similarity(v, w)
        assert isinstance(result, float)

    def test_result_in_minus1_to_1(self):
        rng = np.random.default_rng(99)
        for _ in range(10):
            a = rng.standard_normal(128).astype(np.float32)
            b = rng.standard_normal(128).astype(np.float32)
            sim = Quantizer.cosine_similarity(a, b)
            assert -1.0 - 1e-5 <= sim <= 1.0 + 1e-5


# ── stride ────────────────────────────────────────────────────────────────────

class TestStride:
    def test_float32_stride_is_4x_dims(self):
        q = Quantizer("float32")
        assert q.stride(128) == 512

    def test_float16_stride_is_2x_dims(self):
        q = Quantizer("float16")
        assert q.stride(384) == 768

    def test_int8_stride_equals_dims(self):
        q = Quantizer("int8")
        assert q.stride(256) == 256

    def test_binary_stride_is_ceil_div_8(self):
        q = Quantizer("binary")
        assert q.stride(8) == 1
        assert q.stride(9) == 2
        assert q.stride(64) == 8
        assert q.stride(384) == 48
