# Task 4 · Step 1 — Production table truncation fix · Phase 2: Design

## Decisions
- **Budget:** `_TABLE_CHAR_BUDGET = 1500` chars per table (~400 tokens). Render header +
  rows until the budget is hit, then append `"… (+N more rows)"`. (Configurable constant.)
- **Prose vs table separation:** the Layer-2 prose cap must NOT cut the table. Render prose
  and tables separately; cap prose, append the (already-budgeted) table after it.
- **No format change** — `content.json` keeps all rows; this is render-only.

## DSA / performance
- `_render_table`: O(rows) up to the char budget — bounded. No format/format-version change.
- Net effect: table-bearing prompts grow modestly (intended); worst case bounded by budget.

## SOLID / pattern
- **SRP:** a small pure `_render_table(table, budget)` owns row rendering + the omission note.
- **OCP:** additive helpers; existing callers keep working; behaviour change is the *removal*
  of the silent 5-row cap (intended).
- Minimal, localized to `reader.py`.

## Signatures (locked) — all in `docnest/reader.py`
```python
_TABLE_CHAR_BUDGET = 1500          # max chars rendered per table in a prompt
_SECTION_PROSE_CHARS = 2000        # Layer-2 prose cap (prose only; table added separately)

def _render_table(table: dict, budget: int = _TABLE_CHAR_BUDGET) -> str:
    """Render a table up to `budget` chars; append '… (+N more rows)' if capped."""
    headers = " | ".join(table.get("headers", []))
    lines, used, shown = [headers], len(headers), 0
    rows = table.get("rows", [])
    for row in rows:
        line = " | ".join(row)
        if used + len(line) + 1 > budget and shown >= 1:
            break
        lines.append(line); used += len(line) + 1; shown += 1
    body = "\n".join(lines)
    omitted = len(rows) - shown
    if omitted > 0:
        body += f"\n… (+{omitted} more rows)"
    return f"Table {table.get('table_id', '')}:\n{body}"

def _section_parts(self, section_id: str) -> tuple[str, str]:
    """Return (prose, rendered_tables) for a section. Tables are budget-rendered."""
    section = self.get_section(section_id) or {}
    prose = section.get("text", "")
    tables = "\n\n".join(_render_table(t) for t in section.get("tables", []))
    return prose, tables
```

### Wiring
- `_get_section_text(section_id)` → `prose + "\n\n" + tables` (used by Layer 3/4 + full text).
  Replaces the inline `rows[:5]` rendering. Returns `None` if empty (unchanged contract).
- `_call_llm_section` (Layer 2) → build context as
  `prose[:_SECTION_PROSE_CHARS] + "\n\n" + tables` using `_section_parts(section_id)`, so the
  **table is always included in full (up to its budget)** and never cut by the prose cap.
  (The previously-passed `section_text` arg is no longer truncated for tables.)
- `_call_llm_multi` (Layer 3) / `_call_llm_full` (Layer 4): unchanged prose caps, but they now
  consume the budget-rendered tables via `_get_section_text` / `_build_full_text` (no more 5-row cap).

## Backward compatibility
- Render-only; `.udf` format, `UDF_VERSION`, public API all unchanged.
- `_get_section_text` keeps its `(section_id) -> str | None` signature.

## Tests (Phase 3 preview)
- `_render_table`: >budget table → "+N more rows"; small table → all rows, no note; empty rows.
- `_get_section_text`: 8-row table → rows 6–8 present (not capped at 5).
- Layer-2 path: section with long prose + table → table rows still present after the prose cap.
- Regression: `test_reader.py` still green (confirm no test asserts the old 5-row behaviour).

## ADR
Recorded as **[ADR-0003](../../adr/0003-budgeted-table-rendering.md)**.
