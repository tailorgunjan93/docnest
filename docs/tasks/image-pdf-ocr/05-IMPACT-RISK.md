# Task 3 — Image/Scanned-PDF OCR · Phase 1: Impact & Risk Map

**Decisions locked**
- **Test PDFs are NOT committed** (sensitive personal data). The real-OCR e2e references
  local paths and **skips** when the files (or an OCR engine) are absent — they are never
  copied into the repo or CI.
- **Default OCR engine = EasyOCR** when `ocr=True` and none specified; graceful fallback
  (warn + empty text) when EasyOCR isn't installed.

## Single integration point
`PyMuPDFParser._extract_blocks()` loops `for page in doc`. OCR is added **per page,
additively**: when `self._ocr` is on AND a page yields no usable text layer, render that
page and OCR it via an `IOCRProvider`. OCR-off path stays byte-for-byte unchanged.

## Blast radius

| File | Change | OCR-off behaviour | Impact | Risk |
|---|---|---|---|---|
| `docnest/parsers/pymupdf_pdf.py` | +ctor args (`ocr`, `ocr_provider`, `ocr_languages`, `ocr_dpi`, `ocr_max_px`, `text_layer_min_chars`); per-page OCR fallback | **identical** | Core, additive | **Med** |
| `docnest/providers/ocr.py` | reuse `EasyOCRProvider`/`get_ocr_provider`; maybe a tiny default-resolver | n/a | Low/none | Low |
| `docnest/parsers/factory.py` | optional pass-through of OCR config — **deferred** | unchanged | None now | — |
| `reader.py`/`writer.py`/`models.py` | none | unchanged | None | None |
| `tests/test_pymupdf_ocr.py` | new: offline unit (mock OCR) + gated real e2e | n/a | additive | Low |

## Test surface (verified)
- Only factory tests reference `PyMuPDFParser` (`test_parsers.py:96–117`) — unaffected
  (OCR default off).
- No existing test asserts `PyMuPDFParser` parse output content → low regression surface.

## Backward compatibility
- **OCR default off** → existing `PyMuPDFParser` behaviour and tests unchanged.
- New ctor args additive. No `.udf` / `UDF_VERSION` / public-API change.
- `DoclingPDFParser` untouched here.

## NFR check
- Text pages: O(text) layer check, **no OCR** → ~0 cost (text-layer sample 27s→~0).
- Image pages: OCR bounded by `ocr_dpi`/`ocr_max_px` (downscale); inherent engine cost minimised.
- Privacy/local-first preserved; OCR engine optional & graceful.

## Verdict
**Risk = Med** (touches the parse loop) → mitigated to safe by keeping OCR strictly
additive and gated behind `ocr=True` with an unchanged OCR-off path.
**Impact = Low.** → Eligible for Phase 2 (Design + ADR-0002).

## Open sub-task
The orphaned Docling-OCR WIP (`pdf.py` + `test_parsers.py`, still uncommitted) is kept as
the heavy/high-quality option — commit it via its own short ADR + branch (Roadmap Step A)
so the working tree is clean before/around the lightweight-path work.
