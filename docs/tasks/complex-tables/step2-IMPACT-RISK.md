# Complex Tables · Step 2 — PyMuPDF table extraction (IMPACT & RISK)

## Affected areas
- `docnest/parsers/pymupdf_pdf.py` — `_extract_blocks`, `_build_sections`, new helpers,
  one new `__init__` flag (`extract_tables=True`). **No other module changes.**

## Backward-compatibility
- `TableData` / `Section` / `.udf` / `UDF_VERSION` / public API / PyPI entry points — **unchanged**.
- Default-on, but: PDFs with no detectable tables produce identical output to today.
  `extract_tables=False` restores exact prior behaviour.
- Downstream (writer, reader, viewer) already handle `section.tables` (DOCX/HTML/XLSX
  populate them today) — so populating them from PDF needs no downstream change.

## Risks & mitigations
| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `find_tables` false positives (text mistaken for a table) | Med | Require ≥2 rows AND ≥2 columns; drop degenerate tables. |
| Cell text duplicated in prose | Med | Drop spans whose center is inside a table bbox (de-dup). |
| Table attached to wrong section | Low–Med | Reading-order (page,y0) interleave attaches to the heading above. |
| `find_tables` slower on big PDFs | Low | Per-page, bounded; only the fast path; gated by flag. |
| PyMuPDF version lacking `find_tables` | Low | Guard with `hasattr(page,"find_tables")`; skip gracefully if absent. |

## Risk / Impact rating
- **Impact: Medium** (changes the default PDF parse output — tables now populated).
- **Risk: Low–Medium** — single-file, gated, de-dup + degeneracy guards, fail-soft on any
  PyMuPDF error (never crash parsing). Proceed test-first; gate before merge.

## Test plan (test-first)
- Bordered-table sample PDF → TableData with correct headers/rows attached to its section.
- No cell-text duplication in prose.
- Table-free PDF → unchanged, no tables, no error.
- `extract_tables=False` → no tables (prior behaviour).
- Degenerate 1-col / 1-row "table" → rejected.
- Full regression suite green (regression-first).
