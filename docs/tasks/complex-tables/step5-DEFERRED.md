# Complex Tables · Steps 5–6 — DEFERRED (documented decision)

**Decision (owner-approved 2026-06-04):** Task 2 (complex tables) is **substantially
complete**. The three high-value sub-steps shipped; the remaining two are deferred with
rationale below (not omitted silently).

## Shipped
- Step 1 — budgeted table rendering, drop 5-row cap (ADR-0003)
- Step 2 — PyMuPDF native table extraction (ADR-0006) — *was 100% missing*
- Step 3 — HTML rowspan/colspan grid expansion — *was broken*
- Step 4 — DOCX merged cells, drop harmful dedup — *was buggy*
- (related) deterministic aggregation engine (ADR-0004)

## Deferred — XLSX merged-cell expansion
- **Value: Low.** XLSX already scores highest in the eval (9.6/10). Merges in spreadsheets
  are mostly cosmetic title/header cells; merged *title rows* are already handled (skipped).
- **Cost: real.** openpyxl exposes `merged_cells.ranges` **only in normal mode**; the parser
  uses `read_only=True` to honour the **bounded-memory NFR** for large sheets. Verified:
  read-only worksheets raise `AttributeError` on `merged_cells`.
- **Conclusion:** not worth trading the memory NFR for low value. If revisited, use a
  **bounded** approach: expand merges via normal-mode load only for files under a size
  threshold; keep `read_only` for large files.

## Deferred — multi-row / hierarchical headers
- **Value: uncertain.** No eval failure was attributable to multi-row headers.
- **Cost/complexity: Medium.** Reliably distinguishing a sub-header row from a data row is
  ambiguous and error-prone; a naive heuristic risks regressions on currently-correct tables.
- **Conclusion:** defer as a separate, evidence-driven task if/when a real case appears.

## Re-open criteria
Revisit either item if a concrete document/eval case shows lost accuracy traceable to it.
