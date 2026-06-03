# Task 1 — Path/Schema Compaction · QA / User Document

## What "working" means to a user
- I can convert a document and **share the `.udf` without leaking my computer's paths**.
- Everything else (querying, inspecting, viewing) behaves **exactly as before**.
- My **old `.udf` files still open and answer questions**.

## Test scenarios (functional + e2e)
1. **Windows absolute path** → convert → `catalogue.json` `source` == `"<file>.ext"`
   (basename only, no `D:\...`).
2. **Relative path input** → convert → still basename, no surprise.
3. **Opt-in flag** (`include_source_path=True` / `--include-source-path`) → full path
   preserved verbatim.
4. **Open a pre-existing `.udf`** (absolute `source` inside) → `inspect`, `query`,
   `view` all succeed unchanged.
5. **Query parity** → same question on a doc gives the same answer/citation as before.
6. **HTML viewer** → renders identically (it never used `source`).
7. **Library add** inside vs outside the library folder → relative/alias preferred.

## Edge / negative cases
- File name with **spaces**, **unicode**, or **no extension**.
- **Folder conversion** (library mode) — sanitisation applies to each document.
- Very long original path — must not appear anywhere in the `.udf`.
- Duplicate basenames across docs — confirm `doc_id` still disambiguates (doc_id is
  unaffected by this change).

## Regression view (must not break)
- **Full unit/integration/functional/e2e suite green.**
- **RAG accuracy suite unchanged** (no retrieval code touched) — protects the 9.55/10
  Charter metric.
- Existing parser `source` tests (`test_csv_parser`, `test_md_parser`, `test_parsers`)
  **stay green** (they assert on parser output, untouched).
- Large-PDF / image-PDF / complex-table behaviour **unchanged** (out of scope, but must
  not regress).

## New regression tests to add (Phase 3)
- `catalogue.json` `source` has no absolute path by default.
- Opt-in flag round-trips the full path.
- Loading a fixture `.udf` that contains an absolute `source` still works (back-compat).
