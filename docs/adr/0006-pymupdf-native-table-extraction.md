# ADR-0006 — Native table extraction in PyMuPDFParser (default-on)

- **Status:** Accepted
- **Date:** 2026-06-04
- **Deciders:** Gunjan Tailor (owner)
- **Related:** docs/tasks/complex-tables/step2-DESIGN.md + step2-IMPACT-RISK.md,
  ADR-0003 (budgeted table rendering), ADR-0004 (aggregation)

## Context
`PyMuPDFParser` — the fast, default, no-ML path used for most text PDFs — imported
`TableData` but **never produced one**. So text-PDF tables vanished on the fast path, and
the budgeted-rendering (ADR-0003) and aggregation (ADR-0004) work had no PDF tables to act
on. PyMuPDF ships `page.find_tables()` (already a required dependency); validated on the
bordered sample → clean header + rows.

## Decision
Populate `section.tables` in `PyMuPDFParser` via `page.find_tables()`, **default-on**
(`extract_tables=True`). Each detected table → `TableData` (first row = headers; rest =
rows, padded/trimmed to header width). Tables are placed in **reading order** (page, then
`y0`) so they attach to the heading above them; spans inside a table's bbox are dropped to
avoid duplicating cell text in prose. Degenerate candidates (< 2 rows or < 2 cols) are
rejected; any PyMuPDF error is fail-soft (no tables, never a crash).

## Consequences
- **Positive:** the most-used PDF path now yields structured tables → correct multi-row
  table answers + aggregation on text PDFs; no new dependency.
- **Neutral:** `TableData`/`.udf`/`UDF_VERSION`/public API unchanged; downstream already
  consumes `section.tables`. `extract_tables=False` restores exact prior behaviour.
- **Cost / risk:** possible false-positive tables (mitigated by the ≥2×2 guard) and
  table↔section mis-association on unusual layouts (mitigated by reading-order placement).

## Alternatives considered
- **Leave PyMuPDF table-free, require Docling for tables** — rejected: Docling is the heavy
  (ML, ~1GB) path; tables are common in plain text PDFs and shouldn't require it.
- **Attach all page tables to the page's last section** — rejected: mis-attaches a table
  that precedes a later heading; reading-order placement is barely more code and correct.
- **Keep table text as prose only** — rejected: loses structure that ADR-0003/0004 need.
