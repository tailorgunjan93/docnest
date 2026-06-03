# Task 4 — Complex Tables · BA / Functional Document

## WHY
Tables carry the densest facts, but DocNest loses them in four ways:
1. **Row truncation (highest impact):** at query time the LLM sees only the **first 5 rows**
   of any table (`reader._get_section_text` → `rows[:5]`), even though all rows are stored.
   → wrong max/sum/lookup on multi-row tables. This matches documented benchmark errors
   (#1 "highest monthly revenue → wrong month", #2 "total ARR off, 4 accounts missing").
2. **Multi-row / hierarchical headers** collapse to one ambiguous header row, so column
   meaning (e.g. "Q3" over "Revenue") is lost.
3. **Merged cells (rowspan/colspan)** misalign columns in HTML/DOCX/XLSX (lossy heuristics).
4. **PyMuPDF (the fast/default + OCR path) extracts NO tables** → text-PDF tables vanish
   on the fast path.

## WHAT (required behaviour)
1. **LLM context includes all/most table rows**, bounded by a token budget; if any rows are
   dropped, say so (e.g. "… +N more rows").
2. **Multi-row/hierarchical headers** are flattened into clear combined column labels
   (e.g. `Q3 — Revenue`), preserving meaning in a single header row.
3. **Merged cells** are expanded into a full rectangular grid (span value repeated) so every
   column lines up.
4. **PyMuPDFParser extracts tables** natively (PyMuPDF `find_tables`) → `TableData`.

### Acceptance criteria
1. A 12-row revenue table → "highest month" / "total" answered **correctly** (not limited to 5 rows).
2. An HTML table with `rowspan`/`colspan` → aligned `headers`/`rows` (no shifted cells).
3. A 2-row header table → single header row with combined labels.
4. `PyMuPDFParser` on a text PDF containing a table → at least one `TableData` with headers+rows.
5. Full suite green; **RAG accuracy ≥ 9.55** (ideally higher) — no regression.

### Non-goals
- Tables nested inside cells; free-form/borderless layout reconstruction; charts/figures.
- Changing the `.udf` format (`TableData` stays `{headers[], rows[]}`).

## HOW (functional flow)
Parsers emit rectangular `TableData` (spans expanded, headers flattened) → stored in full →
the reader feeds as many rows as the token budget allows. Users get correct table answers.

### Edge cases
- Very large tables → token-budgeted truncation with an explicit "+N more rows" note.
- Ragged/partial spans, empty cells → padded to a clean grid.
- Tables with no header → first row treated as header (current behaviour).
