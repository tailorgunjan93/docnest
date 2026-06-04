# Complex Tables · Step 3 — HTML rowspan/colspan expansion (DESIGN)

## Problem
`HTMLParser._extract_table` read `<tr>` cells linearly, ignoring `rowspan`/`colspan`. Spanned
tables therefore **misaligned columns**: a `colspan=2` cell took one slot; a `rowspan` cell
was missing from the rows it should carry into.

## Approach — standard grid placement (`_expand_grid`)
Write each cell into **every** `(row, col)` it covers; skip positions already filled by a
rowspan from above:
- `colspan=N` → value repeated across N columns.
- `rowspan=M` → value written into the same column for M rows.
- Build a dense rectangular grid from the placement map → `headers = grid[0]`, `rows = grid[1:]`.

Complexity O(cells × span area), bounded. Pure-Python; no new dependency (bs4 already required).

## Backward-compat / risk
- `TableData`/`.udf`/API unchanged. Plain (span-free) tables produce identical output
  (validated by `test_simple_table_still_works` + full suite, 0 regressions).
- Malformed span attributes fall back to span=1 (try/except).

## Acceptance
- colspan repeats value; rowspan carries value down; combined spans align to header width;
  plain tables unchanged. (tests/test_html_tables.py — 4 tests, green.)
