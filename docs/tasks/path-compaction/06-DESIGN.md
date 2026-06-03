# Task 1 — Path/Schema Compaction · Phase 2: Design

## 1. DSA pass (efficiency)
- Operation is a single pure transform per document: `O(1)` documents × `O(len(source))`
  string work (one `"://"` scan + one `Path(...).name`). Negligible time/space.
- No data-structure choice needed; no NFR budget risk.

## 2. Architecture / SOLID
- **Single Responsibility:** `UDFWriter` owns *what goes into the archive*, so the
  sanitisation belongs at the write boundary — not in parsers or models.
- **Open/Closed:** added via **additive optional params**; existing callers keep working.
  The *default value* changes (privacy-by-default) but the **schema/version does not**,
  and no consumer reads the field (verified Phase 1).
- **Minimal impact:** `Document.source` / `RawDocument.source` stay the real path
  (parsers + their tests untouched). Only the *persisted* value changes.
- **Pattern:** keep the existing **Builder** (`UDFWriter`); extract a tiny **pure
  function** `_sanitise_source()` so the rule is unit-testable in isolation.

## 3. Wrapper / dependency
- No external module involved → no wrapper required. Pure stdlib `pathlib`.

## 4. Edge case: URLs vs local paths
Connector sources are URLs (`connectors/github.py` → `html_url`). Basename-ing a URL
would corrupt it. Rule: **if `source` contains `"://"`, treat it as an already-portable
reference and keep it as-is; otherwise return the basename.**

## 5. File-by-file code plan (exact signatures)

### `docnest/writer.py`
```python
# module-level pure helper (unit-testable)
def _sanitise_source(source: str, keep_full: bool = False) -> str:
    if keep_full:
        return source
    if "://" in source:          # URL (connector) — already portable, not a local path
        return source
    return Path(source).name      # local path -> basename only

class UDFWriter:
    def write(
        self,
        doc: Document,
        output_path: str,
        include_originals: bool = False,
        include_source_path: bool = False,   # NEW, default = sanitise
    ) -> str: ...

    def _build_catalogue(self, doc: Document, include_source_path: bool = False) -> dict:
        # "source": _sanitise_source(doc.source, include_source_path)
        ...
```

### `docnest/pipeline.py`
```python
def convert(
    self,
    source: str,
    output: Optional[str] = None,
    include_originals: bool = False,
    meta: Optional[DocMeta] = None,
    include_source_path: bool = False,       # NEW, threaded to writer.write
) -> str: ...
```

### `docnest/cli.py`
```python
include_source_path: bool = typer.Option(
    False, "--include-source-path",
    help="Store the full original file path in the .udf (default: basename only)",
)
# pass include_source_path=include_source_path into pipeline.convert(...)
```

### Out of scope for this change (kept minimal)
- `docnest/library.py` relative/alias `udf_path` → **separate follow-up step** (its own
  DoR/Phase 0). Keeps Task 1 a single, low-risk change.

## 6. Tests to write first (Phase 3 preview)
- **Unit (pure):** `_sanitise_source` → basename for local path; full path when
  `keep_full=True`; URL preserved unchanged; path with spaces/unicode/no-extension.
- **Integration:** `UDFWriter.write()` default → `catalogue.json` `source` == basename;
  with `include_source_path=True` → full path.
- **E2E:** `pipeline.convert()` default → `.udf` has no absolute path; CLI flag round-trips.
- **Regression / back-compat:** load a fixture `.udf` containing an absolute `source`
  → `UDFIndex.load()` + `query()` succeed.

## 7. ADR
Recorded as **[ADR-0001](../../adr/0001-sanitise-source-at-write-boundary.md)**.
