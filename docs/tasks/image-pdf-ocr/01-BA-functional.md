# Task 3 — Image/Scanned-PDF OCR · BA / Functional Document

## WHY
Scanned/image PDFs carry their text as **pixels**, not characters. Today docnest's fast
parser (`PyMuPDFParser`) extracts **nothing** from them, and the ML parser
(`DoclingPDFParser`) is heavy and (in some envs) fragile. Real example: a 1-page, 5.2 MB
Hindi image PDF (a 1-page scan) → PyMuPDF extracts **0 chars**. Users with scanned docs —
**in Hindi and English** — get empty knowledge bases. This blocks the "works on
everything" mission and the **Reliable** pillar.

## WHAT (required behaviour)
- `PyMuPDFParser` gains **optional OCR** (default **off** — back-compat).
- **Per page:** if the page has a usable **text layer**, use it (no OCR); if it is
  **image-only**, render the page and OCR it.
- OCR runs through the existing **`IOCRProvider`** wrapper (Tesseract or EasyOCR),
  with configurable **languages** (e.g. `["hi", "en"]`).
- Must be **fast**: never OCR a page that already has text; OCR cost is bounded
  (downscale large images / tunable DPI).
- `DoclingPDFParser` OCR remains available as an opt-in **high-quality** option.

### Acceptance criteria
1. The Hindi image sample with OCR on → **Devanagari text extracted** (≥ ~400
   Devanagari chars, coherent).
2. The text-layer sample → **no OCR performed**; text comes from the layer; **fast**.
3. Pure text PDFs → behaviour **unchanged**; **no OCR** by default.
4. OCR **off by default**; enabling needs an explicit option + an installed engine.
5. Engine missing → **graceful** (no crash; clear signal), tests skip.
6. Full suite green; existing PyMuPDF/text tests unchanged.

### Non-goals
- Not replacing Docling; not GPU; not guaranteeing perfect OCR accuracy.
- Not handwriting; not non-PDF images (separate).

## HOW (functional flow)
1. User runs OCR-enabled parse on a PDF.
2. For each page: text-layer present? → use it. Else → render image → OCR (hi/en) → text.
3. Sections built from recovered text; downstream pipeline unchanged.

### Edge cases
- Mixed PDF (some text pages, some scanned) → OCR only the scanned ones.
- Very large page image → downscale before OCR.
- Tiny/garbage text layer → threshold decides OCR vs layer.
- No OCR engine installed → skip gracefully.
