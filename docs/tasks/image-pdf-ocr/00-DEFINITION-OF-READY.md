# Task 3 — Image/Scanned-PDF OCR (fast path) · Definition of Ready

- **Goal (one sentence):** Reliably and *quickly* extract text (Hindi + English) from
  scanned/image PDFs by OCR-ing only image-only pages via a lightweight
  PyMuPDF→`IOCRProvider` path, reusing a page's text layer when present.
- **Traces to Charter:** ✅ **Reliable** (works on scanned docs) + **Fast/Cost-Effective**
  (skip OCR on text pages; bypass Docling) + the "works on everything" mission.
- **Owner:** Gunjan Tailor. **Priority:** Plan-A Task 3 (image PDFs).
- **Acceptance criteria drafted:** ✅ (BA doc).
- **Owner go:** ✅ ("start phase 0"; chose lightweight path + skip-text-pages).
- **Real test data captured:** ✅ (see Dev doc — a Hindi image sample + a text-layer sample, timed).

**DoR GATE: PASSED** → Phase 0 documented below.
