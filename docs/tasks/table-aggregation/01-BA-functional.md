# Task — Deterministic Table Aggregation · BA / Functional Document

## WHY
The eval proved DocNest **retrieves the right table and puts every row in the prompt**,
then **delegates the arithmetic to the LLM** — which is unreliable. Concrete failures:
- **Acme Q8** ("total ARR from Enterprise-tier rows = 7,600"): full table in context,
  LLM returned an **empty answer** → 0/10, at both 1024 and 2048 token caps.
- **Acme Q1/Q2** (column-sum / row-sum): LLM got the result but inconsistently formatted.

Summing, counting, max/min, and averaging over a column — optionally filtered by another
column — is a **deterministic** operation. DocNest already stores tables as structured
`{headers[], rows[]}`. The reasoning belongs **in the library**, not the model.

## WHAT (required behaviour)
1. Given a `TableData`, compute **sum / count / min / max / avg** over a named column.
2. Support an optional **row filter** ("where tier = Enterprise") on another column.
3. **Parse messy numeric cells** deterministically: `$4,050`, `12 550`, `99.97%`,
   `1.24 billion`, `5.8x`, `23,400` → canonical floats.
4. **Resolve column names fuzzily/case-insensitively** ("ARR" ≈ "ARR (USD thousands)").
5. Return a **structured result** (value + which rows/cells contributed) so a caller can
   render an exact answer with **zero LLM tokens**, or fall back gracefully if the table
   can't satisfy the query.

### Acceptance criteria
1. Acme Top Accounts table + `sum(ARR) where tier=Enterprise` → **7600** exactly.
2. Q1 Revenue table + `sum(Q1)` → **12550**; Q2 `max(Annual Total)` → DataSync Pro / 23400.
3. `parse_number` round-trips the messy-cell set above to the right floats (unit-tested).
4. Unknown column / non-numeric column → **explicit "cannot answer"**, never a wrong number
   and never a crash.
5. Full regression suite green; no `.udf`/public-API/format change.

### Non-goals
- Natural-language → query parsing (that's the query-intent router, a later task).
- Multi-table joins, group-by, pivots, percentages-of-total (future).
- Changing `TableData` (`{headers[], rows[]}` stays exactly as is).
- Wiring into the reader's query path (separate, gated follow-up).

## HOW (functional flow)
`TableData` → `TableQuery` wrapper → resolve column → parse numeric cells (skip blanks /
non-numeric) → optional filter → aggregate → `AggregationResult{op, value, unit, n_rows,
contributing_rows}`. A caller (reader Layer, or a future router) uses the value directly.

### Edge cases
- Mixed text/number cells in a column → numbers parsed, non-numbers skipped (counted in a
  `skipped` tally).
- Empty table / empty filtered set → result `value=0` for count, `None` + reason otherwise.
- Currency/percent/unit mixed in one column → magnitudes aggregated; dominant unit reported.
- Duplicate or whitespace-padded headers → normalized before matching.
