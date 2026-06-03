# ADR-0001: Sanitise `source` at the write boundary (privacy-by-default)

- **Status:** Accepted
- **Date:** 2026-06-03
- **Owner:** Gunjan Tailor
- **Related task:** [Task 1 — Path/Schema Compaction](../tasks/path-compaction/)

## Context
A `.udf` is a shareable artifact, but `catalogue.json` currently embeds the author's
**absolute source path** (e.g. `C:\Users\<username>\Documents\sample_report.md`), leaking
username, directory layout, and OS. This conflicts with the Charter's **Secure** pillar
and the "input custody / dead-padding" principle. Phase 1 verified that **no consumer**
(`reader`, `viewer`, library) reads the stored `source` field.

Constraints: must not change retrieval/accuracy, must keep old `.udf` files readable,
must not break parser tests that assert on `RawDocument.source`.

## Decision
Sanitise `source` **only at the write boundary** (`UDFWriter._build_catalogue`) via a
pure helper `_sanitise_source(source, keep_full)`:
- Default: store the **basename** (`sample_report.md`).
- If `source` is a URL (`"://"`), keep it verbatim (already portable — connector sources).
- Opt-in `include_source_path=True` restores the full path.
`RawDocument.source` / `Document.source` remain the real path for internal use.

## Options considered
- **A (chosen): sanitise at write boundary, basename default.** Single change point; no
  schema/version change; parsers + tests untouched; privacy-by-default.
- **B: store a `doc_id` alias instead of basename.** More compact but loses the original
  filename/extension; less human-friendly. Rejected.
- **C: change `RawDocument.source` in parsers.** Wider blast radius; breaks parser
  `source` tests; parsers legitimately need the real path. Rejected.
- **D: bump `UDF_VERSION` / add new field.** Unnecessary — this is a value change to an
  existing field, not a schema change. Rejected (avoids migration cost).

## Consequences
- **Positive:** shared `.udf` leaks no machine info; more portable; aligns with Secure.
- **Trade-off:** the *default* stored value changes for programmatic callers of
  `UDFWriter.write()` (full path → basename). Deliberate (privacy-by-default); old
  behaviour available via `include_source_path=True`.
- **Success Metrics:** accuracy/speed/memory/cost unaffected; **privacy improved**.
- **Backward-compatibility:** old `.udf` files (absolute `source`) still load and query
  unchanged; no `UDF_VERSION` bump; public API additive-only.
