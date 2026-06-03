# Task 3 — Image/Scanned-PDF OCR · Dev / Technical Document

## Real test data (captured this session)
Environment: Store Python 3.11, `easyocr`+`torch 2.12 cpu` installed; `docling` **broken**
(import fails: `tokenizers==0.23.1` vs required `<=0.23.0`); no tesseract binary.

| PDF | pages | text layer | OCR (EasyOCR hi+en, CPU) | result |
|---|---|---|---|---|
| `dhundhotsav` (Hindi image) | 1, 5.2 MB | 0 chars | render 0.83s + **OCR 50.7s** | 667 chars, **526 Devanagari**, coherent ✅ |
| `TMJ` (English) | 1, 2 KB | 35 chars | **OCR 27.4s** → only 24 chars (worse!) | proves: **use the text layer, don't OCR** |
| reader build + models | — | — | 13.0s one-time | amortised |

**Conclusions:** (1) OCR is the cost — skip it whenever a text layer exists. (2) The
PyMuPDF→`IOCRProvider` path works **without Docling**. (3) Downscaling large images is the
lever for image-page OCR time.

## Current code (read)
- `parsers/pymupdf_pdf.py` — `_extract_blocks()` uses `page.get_text("dict")`; **no OCR**.
- `providers/ocr.py` — `IOCRProvider` + `TesseractOCRProvider` + `EasyOCRProvider`
  (`extract_text(image_bytes) -> str`, never raises) — **exists but unused by parsers**.
- `parsers/pdf.py` (uncommitted WIP) — Docling OCR via `ocr_engine`/`ocr_lang` +
  `_sections_from_texts` fallback. Kept as the **heavy/high-quality** option.

## Design (lightweight path — chosen)
Add OCR to `PyMuPDFParser`, behind the existing `IOCRProvider` wrapper:
- New ctor args (additive, default off): `ocr: bool = False`,
  `ocr_provider: IOCRProvider | None = None`, `ocr_languages: list[str] | None = None`,
  `ocr_dpi: int = 200`, `ocr_max_px: int = 2000` (downscale cap),
  `text_layer_min_chars: int = 20` (skip-OCR threshold).
- Per page: `txt = page.get_text("text")`; if `len(txt.strip()) >= text_layer_min_chars`
  → use it (current behaviour). Else render `page.get_pixmap(dpi=ocr_dpi)`, downscale to
  `ocr_max_px`, `ocr_provider.extract_text(png)` → section text.
- **Wrapper rule:** all OCR via `IOCRProvider`; no direct easyocr/tesseract calls in the parser.

## Backward compatibility
- OCR **default off** → existing PyMuPDF behaviour/tests unchanged.
- New ctor args additive. No `.udf`/`UDF_VERSION`/public-API breakage.
- `DoclingPDFParser` OCR untouched (heavy option); the WIP gets committed as that option.

## DSA / performance
- Text-layer check: O(page text) — negligible; **eliminates OCR on text pages** (TMJ 27s→~0).
- Downscale: caps OCR input pixels → bounds per-image OCR time.
- Per-page OCR is O(pixels); inherent to the engine — we minimise *when* and *how big*.

## Risks
- EasyOCR/torch heavy + slow on CPU (inherent) → mitigate via skip-text-pages + downscale;
  document that GPU/Tesseract are faster for some workloads.
- Optional engine not installed → graceful skip (NullOCRProvider / clear message).

## Files likely touched
- `docnest/parsers/pymupdf_pdf.py` (OCR path) · `docnest/providers/ocr.py` (only if interface needs a tweak)
- `docnest/parsers/pdf.py` + `tests/test_parsers.py` (commit the WIP Docling-OCR as heavy option)
- `tests/test_pymupdf_ocr.py` (new) · ADR-0002
