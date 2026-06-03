# Task 3 — Image/Scanned-PDF OCR · QA / User Document

## What "working" means to a user
- A scanned PDF (Hindi or English) yields **searchable text**, not an empty doc.
- It's **fast**: pages that already have text are never OCR'd.
- Nothing changes for normal text PDFs; OCR is opt-in.

## Test scenarios
1. **Hindi image PDF** (`dhundhotsav`) + OCR on → ≥ ~400 Devanagari chars, coherent
   (names/date/venue present). *(real fixture)*
2. **Text-layer page** (`TMJ`) → **no OCR call**; text from layer; sub-second.
3. **Pure text PDF** (e.g. an eval paper) → identical output with OCR off.
4. **OCR off by default** → no engine needed, no behaviour change.
5. **Language config** `["hi","en"]` honoured.
6. **Engine missing** → graceful (no crash; section empty or clear warning).
7. **Mixed PDF** (text + scanned pages) → only scanned pages OCR'd.
8. **Large image** → downscaled before OCR (bounded time).

## Performance acceptance
- Text page OCR time ≈ 0 (skipped).
- Image page OCR time bounded by `ocr_dpi`/`ocr_max_px`; downscale reduces it measurably.
- One-time model load acceptable (~13s for EasyOCR), amortised across pages.

## Regression view (must not break)
- Full unit/integration/functional suite green.
- Existing `PyMuPDFParser` text tests unchanged (OCR default off).
- RAG accuracy suite unaffected (ingestion-only change).
- `DoclingPDFParser` text path unchanged.

## New tests (Phase 3)
- **Unit (offline, mock OCR):** text-layer-present → OCR provider **not** called; image-only
  page → provider called once; downscale caps dimensions; languages passed through;
  engine-missing → graceful.
- **Gated real-OCR e2e:** run `dhundhotsav` (assert Devanagari extracted) + `TMJ`
  (assert text-layer used, no OCR) — **skipped** when no engine / fixtures absent, like the
  CLI e2e gate.
