# Complex Tables · Step 2 — PyMuPDF native table extraction (DESIGN)

## Problem
`PyMuPDFParser` (the fast/default text-PDF path) extracts **zero tables** — it imports
`TableData` but never builds one. Text-PDF tables are lost on the fast path, so the
already-shipped budgeted rendering (Step 1) and the aggregation engine have nothing to work
with for the most common PDF case. (Validated: PyMuPDF `find_tables()` cleanly detects the
bordered sample table → header `['Region','Q1','Q2','Q3']` + 3 rows.)

## Approach
Use PyMuPDF `page.find_tables()` and attach each detected table to the section it sits under.

1. **Extract** per page: `page.find_tables()` → for each table, `t.extract()` (list of row
   lists) and `t.bbox`. First non-empty row → `headers`; the rest → `rows`. Build `TableData`.
2. **De-duplicate** prose: a table's cell text also appears as normal spans. Drop spans whose
   bbox center lies inside any table bbox so cell values aren't repeated in `section.text`.
3. **Associate** by reading order: tag each text span and each table with `(page_index, y0)`;
   within a page, order items by `y0`. A table pseudo-item flows through `_build_sections`
   and attaches to the **current** section (the heading immediately above it).

## Code changes (PyMuPDFParser only)
- `_extract_blocks` → emit an **ordered** item stream carrying `(page, y0)`:
  text items `{"text","size","bold","y0","page"}` **plus** table items
  `{"kind":"table","table":TableData,"y0","page"}`; per-page sort by `y0`; drop in-table spans.
- `_build_sections` → on a `kind=="table"` item: `current.tables.append(item["table"])`
  (create the "Introduction" section if none yet). Text handling unchanged.
- New helpers: `_extract_page_tables(page) -> list[tuple[float, TableData]]` and a bbox
  containment check. **Behind the existing PyMuPDF wrapper**; no new dependency (find_tables
  ships with PyMuPDF, already required).
- New `__init__` flag `extract_tables: bool = True` (off → exact current behaviour).

## DSA / complexity
- find_tables: PyMuPDF-internal (ruling/segmentation). Our work is O(spans + tables) per page
  for the y-sort + containment test. Bounded; no extra model/network.

## SOLID / patterns
- **SRP:** table extraction isolated in `_extract_page_tables`; association is one branch in
  the existing section builder.
- **Open/Closed:** gated by `extract_tables`; default-on but trivially disablable.
- **Backward-compat:** `TableData` unchanged; `.udf`/`UDF_VERSION`/public API unchanged.
  Empty/again-text PDFs behave exactly as before (no tables found → no change).

## Acceptance
1. Sample bordered-table PDF → the section under "Revenue Summary" carries a `TableData`
   with headers `['Region','Q1','Q2','Q3']` and 3 data rows.
2. Cell values are **not** duplicated in that section's prose text.
3. A table-free text PDF (e.g. the resume fixture) → unchanged sections, no tables, no error.
4. Full regression suite green.
