# Task 4 — Complex Tables · Dev / Technical Document

## Current state (code read) + per-area plan

### 1. Row truncation — `reader.py._get_section_text` (HIGH value, LOW risk)
```python
rows = "\n".join(" | ".join(row) for row in table.get("rows", [])[:5])   # <-- 5-row cap
```
`content.json` already stores **all** rows (`writer._build_content` → `t.rows`). Only this
*rendering* truncates. **Fix:** render rows up to a **token/char budget** (e.g. ~1500 chars
per table, configurable), append `"... (+N more rows)"` when capped. Pure rendering change —
no format/parser change. Also applies to Layer-4 full-text builder (same helper).

### 2. Multi-row / hierarchical headers — `models.py` + parsers (MED)
`TableData` has a single `headers: list[str]`. Keep it (back-compat); parsers **flatten**
a detected multi-row header into combined labels (`"Q3 — Revenue"`). Optional later: add an
optional `header_rows: list[list[str]] | None` for round-tripping. Detection differs per parser.

### 3. Merged cells / spans (MED–HIGH)
- **HTML** (`html.py._extract_table`): currently reads `tr/td` ignoring `rowspan`/`colspan`
  → cells shift. **Fix:** build a grid, expand spans (repeat value across the spanned cells).
- **DOCX** (`docx.py._extract_table`): dedups *consecutive equal* cells (lossy). **Fix:**
  build a true grid from `row.cells` (python-docx repeats merged content) keyed by position.
- **XLSX** (`xlsx.py`): opens `read_only=True`, which disables `worksheet.merged_cells`.
  **Fix:** read merge ranges (needs `read_only=False`; weigh memory) and fill spanned cells.
- **PDF/Docling:** TableFormer already handles spans — no change.

### 4. PyMuPDF native tables — `pymupdf_pdf.py` (MED, new capability)
PyMuPDF 1.26 (installed) exposes `page.find_tables()` → `TableFinder`; each table:
`tab.extract()` (rows), `tab.header` (header). **Plan:** in `PyMuPDFParser`, per page call
`find_tables()`, convert each to `TableData` (first/`header` row → headers, rest → rows,
normalised width), attach to the current section. Additive; pairs with the OCR fast path.

## Normalisation
`SectionNormaliser` already pads/truncates rows to `len(headers)` (Stage 3) — keep; grid
expansion happens in parsers before normalisation so widths are already consistent.

## Backward compatibility
- `TableData` model unchanged (`headers[]`, `rows[]`) → **no `.udf`/`UDF_VERSION` change**.
- Reader change is render-only. Parser changes additive. Public API unchanged.
- XLSX `read_only=False` is an internal change (more RAM on huge sheets) — make it
  configurable / weigh in design.

## DSA / performance
- Row rendering: O(rows) up to a budget — bounded.
- Span expansion: O(cells) grid fill — linear.
- `find_tables`: PyMuPDF C-level — fast.

## Files likely touched (by step)
`reader.py` (1) · `html.py` (3) · `pymupdf_pdf.py` (4) · `docx.py` (3) · `xlsx.py` (3) ·
`models.py` (2, optional) · tests for each.

## To confirm in design (Phase 2)
- Token-budget value + truncation note format.
- Whether to add optional `header_rows` to `TableData` now or defer.
- XLSX `read_only` trade-off for merged cells.
