# Task 1 — Path/Schema Compaction · Dev / Technical Document

## Where the absolute path enters and flows (code read, end-to-end)

1. **Parsers** set the absolute path as `RawDocument.source`:
   - `parsers/md.py:103`, `xlsx.py:166`, `csv.py:133`, `docx.py:90`, `html.py:62`,
     `pdf.py:232 & 296`, `pymupdf_pdf.py:87` → all `source=str(path)` / `str(path.resolve())`.
2. **Normalizer** copies it through: `normalizer.py:104` → `Document.source = raw.source`.
3. **Writer** is the **only place it is persisted into the `.udf`**:
   - `writer.py:211` → `_build_catalogue()` writes `"source": doc.source` into
     `catalogue.json`.
   - `_build_manifest()` does **NOT** include source (manifest is already clean).
4. **Consumers of the stored `source`:** *(verified)*
   - `reader.py` (`UDFIndex`): loads `catalogue.json` but **never reads `source`** for
     querying, layers, or display.
   - `viewer.py`: renders title/summary/owner/dept/tags/emb_model/etc. — **never reads
     `source`**.
   - ⇒ **No consumer depends on the stored `source` value.** Sanitising it is safe.
5. **Library (separate concept):** `library.py:175` stores `udf_path` as `str(path)`
   (absolute) when the `.udf` is outside the library folder. Secondary hygiene item.

## Technical WHAT/HOW
- **Single change point (minimal impact):** sanitise at the **write boundary** in
  `writer.py._build_catalogue()`. Keep `RawDocument.source` / `Document.source` untouched
  (parsers + their tests rely on the real absolute path).
- **Default:** store `Path(doc.source).name` (basename) in `catalogue.json`.
- **Opt-in:** thread an `include_source_path: bool = False` option from
  `pipeline.convert()` → `UDFWriter.write()` → `_build_catalogue()`. When `True`, keep
  `doc.source` verbatim.
- **CLI:** optional `--include-source-path` flag on `docnest convert`.
- **(Secondary)** `library.py.add()` — prefer relative path; alias to `doc_id` when
  outside the library root.

## Backward-compatibility surface
- **Existing `.udf` files:** still contain absolute `source`; reader/viewer ignore it →
  **load & query unaffected.** No migration needed.
- **`UDF_VERSION`:** unchanged — this is a value change to an existing field, **not** a
  structural/schema change. No bump required.
- **Public API:** only **additive** optional params (default preserves new safe behaviour).
- **Tests that assert absolute path:** `test_csv_parser.py:196`, `test_md_parser.py:106`,
  `test_parsers.py:156` all assert on **`RawDocument.source`** (parser output) — **not**
  touched by this change, so they stay green.

## DSA / performance
- O(1) per document (one `Path(...).name`). Zero memory/latency impact. No NFR budget risk.

## Wrapper / dependency note
- No new/external dependency. Pure stdlib `pathlib`. No wrapper needed (no third-party module).

## Design pattern (preview for Phase 2)
- Keep the **Builder** pattern of `UDFWriter`; add a sanitisation step — Single
  Responsibility preserved (writer owns what goes into the archive). An **ADR** will
  record "sanitise source at write boundary; keep `Document.source` internal."

## Files likely touched
- `docnest/writer.py` (core change + option)
- `docnest/pipeline.py` (pass-through option)
- `docnest/cli.py` (optional flag)
- `docnest/library.py` (secondary, optional)
- `tests/test_writer.py` (+ new assertions); regression test added
