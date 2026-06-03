# Task 4 · Step 1 — Production table truncation fix · Phase 1: Impact & Risk

**Goal:** stop the production `UDFIndex.query` path from silently dropping table rows, so
table aggregation/lookup answers are correct (bring it up to the eval's full-table standard).

## Truncation points in the production path (all in `reader.py`)
| # | Location | Current | Effect |
|---|---|---|---|
| 1 | `_get_section_text` | `rows[:5]` | every table capped to **5 rows** when assembled |
| 2 | `_call_llm_section` (Layer 2) | `section_text[:2000]` | section+table prompt cut at 2000 chars |
| 3 | `_call_llm_multi` (Layer 3) | `text[:600]` per section | 600 chars/section — tables almost entirely cut |
| 4 | `_call_llm_full` (Layer 4) | `full_text[:6000]` | whole-doc cut at 6000 chars |

**Root issue:** #1 is the hard cap; #2–#4 are char budgets that can still chop a large
table even after #1 is fixed. A correct fix addresses #1 and makes the budgets table-aware.

## Planned change (Step 1)
- Render table rows in `_get_section_text` up to a **char/token budget** (default ~1500
  chars/table), append `"… (+N more rows)"` when capped — instead of a flat 5.
- Raise / make table-aware the Layer-2 section cap so a budgeted table isn't re-chopped
  (Layer 2 is the common table-answer path). Keep Layer 3/4 caps but document them.
- All rows remain stored in `content.json` (writer unchanged) — this is render-only.

## Blast radius
| File | Change | Impact | Risk |
|---|---|---|---|
| `docnest/reader.py` | budgeted table rendering in `_get_section_text`; adjust Layer-2 cap | Core query path | **Med** |
| `writer.py` / `models.py` / parsers | none | none | None |
| `.udf` format / `UDF_VERSION` | none (render-only) | none | None |

## Test surface
- `tests/test_reader.py` exists — check whether any test asserts the 5-row behaviour or
  prompt sizes (Phase 3 will confirm; likely none assert `[:5]`).
- New tests: a section with a >5-row table → all rows (up to budget) appear in
  `_get_section_text`; over-budget table → "+N more rows" note; Layer-2 answer sees rows
  beyond #5; small tables unchanged.

## Backward compatibility
- Render-only; no format/version/API change. Existing `.udf` files unaffected.
- Token usage per table-bearing query rises modestly (more rows in context) — bounded by
  the budget; aligns with the eval (which already sends full ≤30-row tables).

## NFR / cost
- Slightly more tokens on table queries (intended — correctness). Budget caps the worst case.
- No latency/memory concern (string assembly).

## Verdict
**Risk = Med** (touches the core query/prompt path) → mitigate by: budget (not unbounded),
"+N more rows" transparency, OCR-off-style additive caution, and full-suite + targeted
reader tests. **Impact = Low** (render-only, no format change). → Eligible for Phase 2.

## Note
This Step does **not** move the 88-Q eval (the eval uses its own full-table assembly, not
`reader._get_section_text`). It fixes the **production** query path. Validated by unit tests.
