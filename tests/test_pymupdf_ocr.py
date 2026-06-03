"""Task 3 — lightweight OCR in PyMuPDFParser (skip-text-pages).

Written test-first (Phase 3): FAILS until the OCR path lands.

- Offline unit tests use synthetic PDFs (fitz) + a spy IOCRProvider — no engine/network.
- A gated real-OCR e2e runs only when DOCNEST_OCR_PDF_DIR is set AND easyocr is installed
  (so CI / machines without the local PDFs skip it; no personal paths are committed).

Run: pytest tests/test_pymupdf_ocr.py -v
"""
from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path

import pytest

from docnest.parsers.pymupdf_pdf import PyMuPDFParser
from docnest.providers.ocr import IOCRProvider


def _has(mod: str) -> bool:
    return bool(importlib.util.find_spec(mod))

# CI installs only ".[dev]" — easyocr/Pillow may be absent. Gate accordingly so the
# suite is environment-independent (no hard dependency on optional OCR packages).
requires_easyocr = pytest.mark.skipif(not _has("easyocr"), reason="easyocr not installed")
requires_pillow = pytest.mark.skipif(not _has("PIL"), reason="Pillow not installed")


# ── Helpers ─────────────────────────────────────────────────────────────────

class SpyOCR(IOCRProvider):
    """Records calls; returns a fixed string. No real OCR."""
    def __init__(self, ret: str = "RECOVERED OCR TEXT FROM IMAGE") -> None:
        self.calls = 0
        self._ret = ret

    def extract_text(self, image_bytes: bytes) -> str:
        self.calls += 1
        return self._ret

    @property
    def backend_name(self) -> str:
        return "spy"


def _text_pdf(tmp: Path) -> str:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72),
                     "This is a real text layer with plenty of characters to read.")
    p = str(tmp / "text.pdf"); doc.save(p); doc.close()
    return p


def _image_only_pdf(tmp: Path) -> str:
    """A PDF page with a drawing but NO text layer (fitz only — no Pillow needed).

    `get_text` returns empty for this page, so it triggers the OCR fallback.
    """
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=400, height=200)
    page.draw_rect(fitz.Rect(20, 20, 380, 180), fill=(0, 0, 0))  # vector, no text
    p = str(tmp / "image.pdf"); doc.save(p); doc.close()
    return p


# ── Unit: skip-text-pages ────────────────────────────────────────────────────

class TestSkipTextPages:
    def test_text_page_does_not_invoke_ocr(self, tmp_path: Path):
        spy = SpyOCR()
        raw = PyMuPDFParser(ocr=True, ocr_provider=spy).parse(_text_pdf(tmp_path))
        assert spy.calls == 0
        joined = " ".join(s.text for s in raw.sections)
        assert "text layer" in joined

    def test_image_only_page_invokes_ocr_once(self, tmp_path: Path):
        spy = SpyOCR("OCR_OUTPUT_XYZ")
        raw = PyMuPDFParser(ocr=True, ocr_provider=spy).parse(_image_only_pdf(tmp_path))
        assert spy.calls == 1
        assert any("OCR_OUTPUT_XYZ" in s.text for s in raw.sections)

    def test_ocr_off_by_default_no_ocr_on_image(self, tmp_path: Path):
        spy = SpyOCR()
        # ocr defaults off -> provider never used even if passed
        raw = PyMuPDFParser(ocr_provider=spy).parse(_image_only_pdf(tmp_path))
        assert spy.calls == 0
        assert all("RECOVERED" not in (s.text or "") for s in raw.sections)


# ── Unit: provider resolution + downscale ────────────────────────────────────

class TestProviderResolution:
    @requires_easyocr
    def test_default_engine_is_easyocr_with_languages(self):
        from docnest.providers.ocr import EasyOCRProvider
        p = PyMuPDFParser(ocr=True, ocr_languages=["hi", "en"])
        assert isinstance(p._ocr_provider, EasyOCRProvider)
        assert p._ocr_provider._languages == ["hi", "en"]

    def test_missing_engine_falls_back_to_null(self, monkeypatch):
        from docnest.providers import ocr as ocrmod
        monkeypatch.setattr(ocrmod.EasyOCRProvider, "available",
                            property(lambda self: False))
        p = PyMuPDFParser(ocr=True)
        assert isinstance(p._ocr_provider, ocrmod.NullOCRProvider)

    @requires_pillow
    def test_downscale_caps_long_edge(self):
        from docnest.parsers.pymupdf_pdf import _downscale_png
        from PIL import Image
        big = io.BytesIO(); Image.new("RGB", (3000, 1000), "white").save(big, "PNG")
        out = _downscale_png(big.getvalue(), 2000)
        w, h = Image.open(io.BytesIO(out)).size
        assert max(w, h) <= 2000


# ── Gated real-OCR e2e (set DOCNEST_OCR_PDF_DIR + install easyocr to run) ─────

_PDF_DIR = os.environ.get("DOCNEST_OCR_PDF_DIR")

requires_real = pytest.mark.skipif(
    not (_PDF_DIR and _has("easyocr")),
    reason="set DOCNEST_OCR_PDF_DIR to a folder with the test PDFs + install easyocr",
)


@requires_real
class TestRealOCR:
    def test_hindi_image_pdf_extracts_devanagari(self):
        pdf = Path(_PDF_DIR) / "dhundhotsav_invitation_2.pdf"
        if not pdf.exists():
            pytest.skip(f"missing {pdf.name}")
        raw = PyMuPDFParser(ocr=True, ocr_languages=["hi", "en"]).parse(str(pdf))
        text = " ".join(s.text for s in raw.sections)
        deva = sum(1 for c in text if "ऀ" <= c <= "ॿ")
        assert deva > 200

    def test_textlayer_pdf_skips_ocr(self):
        pdf = Path(_PDF_DIR) / "TMJ_Exercises_Color_Diagram.pdf"
        if not pdf.exists():
            pytest.skip(f"missing {pdf.name}")
        spy = SpyOCR()
        PyMuPDFParser(ocr=True, ocr_provider=spy).parse(str(pdf))
        assert spy.calls == 0  # has a text layer -> no OCR
