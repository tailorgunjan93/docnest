# ADR-0003: Budgeted table rendering in the query path (drop the 5-row cap)

- **Status:** Accepted
- **Date:** 2026-06-03
- **Owner:** Gunjan Tailor
- **Related task:** [Task 4 · Step 1](../tasks/complex-tables/)

## Context
The production query path (`reader._get_section_text`) rendered only the **first 5 rows**
of any table (`rows[:5]`), and the Layer-2 prompt builder then cut the combined section
text at 2000 chars. So table aggregation/lookup answers in production could be wrong even
though all rows are stored in `content.json`. (The 88-Q eval is unaffected — it has its own
full-table assembly; this is a production-path bug.)

## Decision
Render tables up to a **char budget** (`_TABLE_CHAR_BUDGET = 1500`) with an explicit
`"… (+N more rows)"` note instead of a flat 5-row cap, via a pure `_render_table` helper.
Separate **prose from tables** so the Layer-2 prose cap (`_SECTION_PROSE_CHARS = 2000`)
caps only the prose and the budgeted table is always appended in full. Render-only — no
`.udf` format or `UDF_VERSION` change.

## Options considered
- **A (chosen):** budgeted rendering + prose/table separation. Correct, bounded, transparent.
- **B:** just raise the 5-row cap to N rows. Still arbitrary; Layer-2 char cap still chops it.
- **C:** send the entire table always. Unbounded token blow-up on huge tables.
- **D:** change `content.json`/`TableData`. Unnecessary — data is already complete; bump avoided.

## Consequences
- **Positive:** correct table answers in production; transparent omission note; bounded cost.
- **Trade-off:** modestly more tokens on table-bearing queries (intended; capped by budget).
- **Success Metrics:** Reliable ↑; cost rises slightly but bounded; 88-Q eval score unchanged
  (different path) — validated by unit tests, not the eval.
- **Backward-compatibility:** render-only; existing `.udf` files + API unchanged.
