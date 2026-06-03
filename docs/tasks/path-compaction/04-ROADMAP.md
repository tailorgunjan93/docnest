# Task 1 — Path/Schema Compaction · Final Roadmap

Consolidates the BA, Dev, and QA documents into a sequenced plan.
**Overall expectation: Risk = Low, Impact = Low** (single write-boundary change; no
consumer reads the field; no schema/version change).

| Step | Phase | Action | Risk/Impact | Sign-off |
|---|---|---|---|---|
| 1 | 1 — Impact & Risk | Confirm no consumer reads `catalogue.source`; confirm `test_writer` expectations; write impact map | Low/Low | owner |
| 2 | 2 — Design + ADR | Finalise: sanitise in `_build_catalogue`; `include_source_path` opt-in threaded through pipeline→writer; CLI flag; (optional) library path aliasing. Write ADR-0001. | Low/Low | owner |
| 3 | 3 — Test First | Write failing tests: default basename, opt-in full path, back-compat load of absolute-source fixture. Add to regression suite. | Low | owner |
| 4 | 4 — Implement | Code exactly per plan (writer + pipeline + cli, optional library). | Low | owner |
| 5 | 5 — Verify | Run FULL suite + confirm RAG accuracy + NFR budgets unchanged → ✅ green | — | owner |
| 6 | 7 — Git/Release | Temp branch → all green → merge to main → bump version + CHANGELOG → (batch with later tasks before PyPI) | Low | owner |

## Dependencies / sequencing
- Independent of the robustness tasks (tables/PDFs) — safe warm-up to exercise the protocol.
- Library path-aliasing (secondary) can be split into its own step if it grows.

## Milestones
- **M1:** Phase 0 docs approved (this set).
- **M2:** Design + ADR-0001 approved.
- **M3:** Tests written & failing.
- **M4:** Implemented + full suite green.
- **M5:** Merged to main (release batched with subsequent tasks).

## Open decisions for owner
- **Default source value:** file **basename** (recommended) vs an opaque **doc_id alias**?
- **Release cadence:** ship this alone to PyPI, or batch with the table/PDF work?
