# Complex Tables · Step 4 — DOCX merged cells (DESIGN)

## Problem
`DocxParser._extract_table` deduplicated **consecutive identical values** per row as a
"merged-cell artefact" fix. This was wrong twice over: it (a) misaligned horizontally
merged columns (collapsing the repeated span value) and (b) collapsed *legitimate*
duplicate values (e.g. two cells both "10").

## Approach
python-docx's `row.cells` already returns a full rectangular grid where a merged cell
repeats its value across every position it covers — gridSpan repeats across columns,
vMerge repeats down rows. So keep the grid verbatim (`[cell.text for cell in row.cells]`)
and **remove the dedup**. This aligns columns (value repeated, like HTML colspan) and
preserves real duplicates.

## Backward-compat / risk
- `TableData`/`.udf`/API unchanged. Plain tables identical. Full suite 0 regressions.

## Acceptance (tests/test_docx_tables.py — 4 tests, green)
- gridSpan repeats value & aligns; vMerge carries value down; duplicate values preserved;
  plain table unchanged.
