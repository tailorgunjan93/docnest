# Task 1 — Path/Schema Compaction · Phase 1: Impact & Risk Map

**Decision locked:** default stored `source` = **file basename** (e.g. `sample_report.md`).
**Release:** batched with later tasks (merge to main; PyPI later).

## Single change point
`writer.py._build_catalogue()` — sanitise `doc.source` → `Path(doc.source).name` before
storing. Add opt-in `include_source_path=False` threaded from `convert()` → `write()`.

## Blast radius (every affected area)

| File | Change | Reads `source` today? | Impact | Risk |
|---|---|---|---|---|
| `docnest/writer.py` | Sanitise in `_build_catalogue`; add `include_source_path` param to `write()` | writes it | Core, local | Low |
| `docnest/pipeline.py` | Thread optional `include_source_path` through `convert()`/`process` | no | Additive param | Low |
| `docnest/cli.py` | Add `--include-source-path` flag (default off) | no | Additive flag | Low |
| `docnest/library.py` | (Secondary) prefer relative/alias `udf_path` | uses own `udf_path` | Optional, can split | Low |
| `docnest/reader.py` | none — never reads `source` ✅ | no | None | None |
| `docnest/viewer.py` | none — never reads `source` ✅ | no | None | None |
| `docnest/models.py` | none — `Document.source` stays the real path | n/a | None | None |

## Test surface (verified)
- `tests/test_writer.py` — **no `source` assertions** → safe; we will ADD new ones.
- `tests/conftest.py:86` — fixture `source="test.pdf"` (already basename) →
  `Path("test.pdf").name == "test.pdf"` → fixtures unaffected.
- `tests/test_csv_parser.py:196`, `test_md_parser.py:106`, `test_parsers.py:156` —
  assert on **`RawDocument.source`** (parser output, untouched) → stay green.

## Backward compatibility
- **Old `.udf`** (absolute `source` inside): reader/viewer ignore the field → open & query
  unaffected. **No migration.**
- **`UDF_VERSION`**: unchanged (value change to an existing field, not a schema change).
- **Public API**: only additive optional params; default = new safe behaviour.

## NFR check
- Time/space: **O(1)** per document. No latency/memory regression.
- Privacy: **improves** (Charter "Secure"). Accuracy/retrieval: untouched → 9.55/10 safe.

## Verdict
**Risk = Low. Impact = Low.** Mitigations already inherent: default-safe value, opt-in to
restore old behaviour, additive-only API, no consumer depends on the field.
→ Eligible to proceed to Phase 2 (Design + ADR-0001).
