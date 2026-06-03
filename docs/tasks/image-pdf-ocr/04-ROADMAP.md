# Task 3 — Image/Scanned-PDF OCR · Final Roadmap

Direction (owner-chosen): **lightweight PyMuPDF→IOCRProvider path + skip-text-pages**;
Docling OCR kept as an opt-in heavy/high-quality option.

| Step | Phase | Action | Risk/Impact | Sign-off |
|---|---|---|---|---|
| A | (sub-task) | **Formalise + commit the orphaned Docling-OCR WIP** (`pdf.py` + `test_parsers.py`) as the heavy option — own ADR, run suite, branch→merge | Low/Low | owner |
| 1 | 1 — Impact & Risk | Confirm blast radius of adding OCR to `PyMuPDFParser`; back-compat (OCR off) | Low/Low | owner |
| 2 | 2 — Design + ADR-0002 | Lock signatures (ocr/ocr_provider/ocr_languages/ocr_dpi/ocr_max_px/text_layer_min_chars); skip-text-page rule; downscale; IOCRProvider reuse | Low/Low | owner |
| 3 | 3 — Test First | Offline unit tests (mock OCR) + gated real-OCR e2e on the 2 real PDFs | Low | owner |
| 4 | 4 — Implement | Wire OCR into `PyMuPDFParser` per design | Low/Med | owner |
| 5 | 5 — Verify | Full suite green + real OCR timing (text page ≈0; image page bounded) | — | owner |
| 6 | 7 — Git/Release | Branch → merge → push; batch PyPI with prior tasks | Low | owner |

## Dependencies / notes
- Real fixtures: `dhundhotsav` (Hindi image) + `TMJ` (text layer) — used for the gated e2e.
  Decide whether to commit them to `tests/fixtures/` (privacy: the invitation has family
  names — see open decision).
- EasyOCR/torch already installed locally; Tesseract path also supported via `IOCRProvider`.
- Docling import is broken in this env (`tokenizers` pin) — **out of scope** for the
  lightweight path; note it for a separate env/deps fix.

## Milestones
- M1: Phase 0 docs approved (this set).
- M2: ADR-0002 + design approved.
- M3: tests written (offline green + gated e2e).
- M4: implemented; full suite green; real OCR timing shows skip-text-page win.
- M5: merged to main (release batched).

## Open decisions for owner
1. **Commit the real PDFs as test fixtures?** `dhundhotsav` contains family names/venue
   (personal). Options: (a) don't commit — keep gated e2e pointing at local paths / skip in
   CI; (b) commit a **redacted/synthetic** Hindi image instead; (c) commit as-is. *(default: a)*
2. **Default OCR engine** when `ocr=True` but none specified — EasyOCR (installed, Hindi) vs
   Tesseract (lighter, needs binary)?
