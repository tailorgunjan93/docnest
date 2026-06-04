# Task — Deterministic Table Aggregation · QA / User Document

## What "working" means to a user
A user asks "what's the total ARR from Enterprise customers?" and DocNest returns the
**exact number computed from the table** — not an LLM guess, not an empty answer.

## Test scenarios (map to tests/test_aggregation.py)

### Happy path
- `sum` of a clean integer column → exact total.
- `sum` with a filter (`tier == Enterprise`) → only matching rows summed (Acme Q8 → 7600).
- `max`/`min` → correct extreme; `avg` → mean of numeric cells; `count` → row count.
- Column resolved despite case/whitespace/suffix ("arr" → "ARR (USD thousands)").

### Number parsing (parse_number)
- `"$4,050"`→4050, `"12 550"`→12550, `"99.97%"`→99.97, `"1.24 billion"`→1.24e9,
  `"5.8x"`→5.8, `"23,400"`→23400, `"1,234.56"`→1234.56.
- `""`, `"N/A"`, `"—"`, `"n/a"`, pure text → `None` (skipped, not zero).

### Edge / negative
- Unknown column → `ok=False`, reason mentions the column; **no crash, no wrong number**.
- Non-numeric column for `sum` → `ok=False` with reason (0 numeric cells).
- Empty table → `count`=0 ok; `sum` over empty → `ok=False`.
- Filter matches nothing → `ok=False` (no rows) for sum/avg; `count`=0 ok.
- Mixed unit column → aggregates magnitudes, reports dominant unit; `skipped` counts non-numerics.
- Ragged row (fewer cells than headers) → that cell treated as missing, not a crash.

### Regression view
- Net-new module, imported by nothing → **must not change any existing test outcome**.
- Full suite (`pytest -q`) green before and after.
- Determinism: same input → same output, every run (no randomness, no network, no clock).
