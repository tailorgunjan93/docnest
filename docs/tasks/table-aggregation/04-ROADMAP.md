# Task — Deterministic Table Aggregation · ROADMAP

## Ordered steps
1. **Phase 0 (this set of docs)** — BA / Dev / QA / Roadmap. ✅
2. **ADR-0004** — record the deterministic-aggregation decision + the dependency-free
   wrapper boundary. ✅
3. **Test-first** — write `tests/test_aggregation.py` (parse_number table, aggregation
   happy/edge/negative). Run → **fails** (module absent). 
4. **Implement** `docnest/aggregation.py` to green. Run targeted tests → pass.
5. **Full regression suite** (`pytest -q`) → green, zero regressions.
6. **Gate (owner sign-off)** — review before any merge. **STOP here without explicit go.**
7. *(Future, separate task)* wire `TableQuery` into the reader query path behind the
   query-intent router; add an extractive fallback so answers are never empty.

## Dependencies
- Consumes only `docnest.models.TableData` (read-only). No new third-party deps.
- Independent of the `task/table-truncation-fix` branch (which stays the pure reader fix).

## Milestones
- M1: Phase 0 + ADR committed. 
- M2: tests written (red) → module (green) → full suite green.
- M3: owner review → merge decision (batched with other post-eval work, no PyPI yet).

## Risk / impact
- **Impact: Low** — additive net-new file; nothing imports it until a later gated task.
- **Risk: Low** — pure functions, no external deps, no format/API change, fail-closed.
- Per protocol: proceed because Impact=Low & Risk=Low; backward compatibility fully preserved.
