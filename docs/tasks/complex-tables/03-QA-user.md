# Task 4 — Complex Tables · QA / User Document

## What "working" means to a user
- Asking about a value buried in row 11 of a table gets the **right** answer.
- A "total"/"max"/"which is highest" question over a table is **correct** (all rows seen).
- Tables with stacked headers or merged cells keep their column meaning.
- Tables in plain text PDFs are captured by the fast parser too.

## Test scenarios (per area)
1. **Row truncation:** a 12-row table → "highest value" and "sum" answered using ALL rows
   (not just first 5); a huge table → bounded context + "+N more rows" note.
2. **HTML spans:** a table with `rowspan`/`colspan` → `rows` align to `headers`; spanned
   value repeated; no column shift.
3. **DOCX merged cells:** merged header/data cells → grid aligned, value preserved.
4. **XLSX merged cells:** merged ranges filled; multi-table sheet still split correctly.
5. **Multi-row headers:** 2-row header → single combined-label header row (`"Q3 — Revenue"`).
6. **PyMuPDF tables:** a text PDF with a bordered table → ≥1 `TableData(headers, rows)`.

## Regression view (must not break)
- Full unit/integration/functional suite green.
- **RAG accuracy ≥ 9.55** on the 88-Q suite — and re-run after Step 1 to **measure the gain**
  (truncation fix should fix benchmark errors #1/#2).
- Existing single-header / simple-table tests unchanged.
- `.udf` format + existing files load unchanged.

## New tests (per step, test-first)
- Reader: rows beyond #5 appear in context up to budget; over-budget → "+N more rows" note;
  small table → all rows; Layer-4 full text likewise.
- HTML/DOCX/XLSX: span-expansion unit tests (rowspan, colspan, mixed) → exact grid asserted.
- Multi-row header → combined labels asserted.
- PyMuPDF: synthetic bordered-table PDF (fitz) → `TableData` with expected headers/rows.
- Gated real-PDF table e2e where useful (skip when fixtures/engine absent).
