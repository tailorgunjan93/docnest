# Architecture Decision Records (ADRs)

The permanent "why" behind every significant technical decision in DocNest.

**Rule (from [DEVELOPMENT_PROTOCOL.md](../../DEVELOPMENT_PROTOCOL.md) GATE 2):** a
significant decision is not "done" until its ADR exists here.

## What counts as "significant"
- A new module/interface, a new external dependency, or a new wrapper boundary.
- A change to the `.udf` format, `UDF_VERSION`, or the public API.
- A choice of algorithm/data-structure with a real trade-off (speed/memory/accuracy).
- Anything you'd otherwise have to re-explain or re-litigate later.

## How to add one
1. Copy [`0000-template.md`](0000-template.md) to `NNNN-short-title.md` (next number).
2. Fill it in. Keep it short — one decision per record.
3. Link it from the task's Dev document and the PR.

## Index
- 0000 — Template (not a real decision)
- [0001 — Sanitise `source` at the write boundary (privacy-by-default)](0001-sanitise-source-at-write-boundary.md) — Accepted
- [0002 — Lightweight OCR in PyMuPDFParser (skip text pages); Docling OCR as heavy option](0002-lightweight-pymupdf-ocr.md) — Accepted
- [0003 — Budgeted table rendering in the query path (drop the 5-row cap)](0003-budgeted-table-rendering.md) — Accepted
- [0004 — Deterministic table aggregation in the library (not the LLM)](0004-deterministic-table-aggregation.md) — Accepted
- [0006 — Native table extraction in PyMuPDFParser (default-on)](0006-pymupdf-native-table-extraction.md) — Accepted
- [0007 — Passage chunking for large sections (retrievability)](0007-passage-chunking-for-large-sections.md) — Accepted
- [0008 — Deterministic key-number enrichment (revive the 0-token path)](0008-deterministic-key-number-enrichment.md) — Accepted
- [0009 — Deterministic keywords + extractive Layer 1 (push 0-token to ≥70%)](0009-deterministic-keywords-extractive-layer1.md) — Accepted
