# ADR-0002: Lightweight OCR in PyMuPDFParser (skip text pages), Docling OCR as heavy option

- **Status:** Accepted
- **Date:** 2026-06-03
- **Owner:** Gunjan Tailor
- **Related task:** [Task 3 — Image/Scanned-PDF OCR](../tasks/image-pdf-ocr/)

## Context
Scanned/image PDFs store text as pixels. `PyMuPDFParser` extracts nothing from them; the
only OCR route was `DoclingPDFParser`, which is heavy (torch + transformers + TableFormer)
and fragile in some envs (a `tokenizers` version conflict breaks import). Real test data
(this session): a 1-page Hindi image PDF OCR'd to 526 Devanagari chars via
**PyMuPDF render → EasyOCR**, in ~51s; a text-layer page wasted 27s on OCR for *worse*
output than its existing text layer. So: OCR is the cost, and text pages must not be OCR'd.

Constraints: keep OCR-off behaviour identical; OCR engine optional; reuse the existing
`IOCRProvider` wrapper; local-first.

## Decision
Add **optional OCR to `PyMuPDFParser`** behind the existing `IOCRProvider` abstraction:
- Per page, **use the text layer when present**; OCR only image-only pages.
- Render via PyMuPDF, **downscale** to a max edge, OCR via the provider.
- **EasyOCR is the default** engine when `ocr=True` and none is given (strong Hindi);
  fall back to `NullOCRProvider` (empty text, no crash) when no engine is installed.
- OCR **off by default** (additive ctor args).
- `DoclingPDFParser` OCR is **retained as the opt-in heavy/high-quality option** (the
  orphaned WIP is committed as that option).

## Options considered
- **A (chosen): lightweight PyMuPDF + IOCRProvider, skip text pages.** Fast, few deps,
  reuses the wrapper, bypasses broken/heavy Docling. Matches the measured data.
- **B: Docling-only, optimise it.** Heavy, torch-bound, env-fragile; overkill for scans.
- **C: brand-new separate OCR parser.** Duplicates PyMuPDF page/section logic; more surface.

## Consequences
- **Positive:** scanned PDFs (Hindi/English) become searchable; text pages cost ~0 OCR;
  no torch needed unless OCR is explicitly enabled with EasyOCR.
- **Trade-off:** per-image OCR is still engine-bound slow on CPU (inherent); mitigated by
  skip-text-pages + downscale; Tesseract/GPU available via the provider for speed.
- **Success Metrics:** Reliable ↑ (works on scans), Fast/Cost ↑ (skip text pages), accuracy
  of retrieval unaffected for text PDFs; privacy/local-first preserved.
- **Backward-compatibility:** OCR off by default → no change for existing users; additive
  API; no `UDF_VERSION` bump.
