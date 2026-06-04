# Task — Deterministic Table Aggregation · DEV / Technical Document

## New module: `docnest/aggregation.py`
Pure-Python, **no external dependency**, no network, deterministic. Operates on the
existing `docnest.models.TableData` (`headers: list[str]`, `rows: list[list[str]]`).

### Public surface (additive only)
```python
def parse_number(cell: str) -> float | None
    # "$4,050"→4050.0  "12 550"→12550.0  "99.97%"→99.97  "1.24 billion"→1_240_000_000.0
    # "5.8x"→5.8  ""/"N/A"/"—"→None

class TableQuery:
    def __init__(self, table: TableData)
    def resolve_column(self, name: str) -> int | None      # fuzzy, case-insensitive
    def numeric_column(self, name: str) -> list[tuple[int, float]]   # (row_idx, value)
    def filter_rows(self, col: str, op: str, value: str) -> list[int]  # eq/contains/gt/lt
    def aggregate(self, op: str, column: str,
                  where: tuple[str, str, str] | None = None) -> "AggregationResult"

@dataclass
class AggregationResult:
    ok: bool
    op: str                     # sum|count|min|max|avg
    value: float | None
    unit: str | None            # dominant unit symbol if any ($, %, x)
    n_rows: int                 # rows that contributed
    skipped: int                # non-numeric cells skipped
    reason: str                 # "" if ok else why it could not answer
```

### Algorithms & complexity
- **`parse_number`** — ordered regex/cleanup: trim → strip currency/`,`/space-thousands →
  detect trailing `%`/`x`/unit → apply magnitude words (k=1e3, million=1e6, billion=1e9) →
  `float`. O(len cell). Regular-language recognition; no model.
- **`resolve_column`** — exact (normalized) match → substring/token-overlap fallback
  (Jaccard on lowercased tokens), highest score wins, tie→first. O(cols × tokens).
- **`filter_rows`** — linear scan; `eq`/`contains` on normalized strings, `gt`/`lt` on
  parsed numbers. O(rows). Relational σ (select).
- **`aggregate`** — σ (optional filter) then fold over `numeric_column`. O(rows).
  Relational aggregate (Σ/count/min/max/avg).
- **unit detection** — modal unit symbol among contributing cells.

### SOLID / patterns
- **SRP:** module does one thing — deterministic numeric aggregation over a table.
- **Open/Closed:** new ops added via a small dispatch dict, not by editing callers.
- **Dependency-free wrapper:** `TableQuery` wraps `TableData`; callers depend on the
  result dataclass, not internals (stable seam for the future reader/router wiring).
- **Fail-closed:** any ambiguity/parse failure → `ok=False` + `reason`, never a guess.

### Backward-compatibility surface
- No change to `TableData`, `.udf` layout, `UDF_VERSION`, public API, or PyPI entry points.
- Net-new file; nothing imports it yet → zero blast radius until explicitly wired (later task).

### Reading the code it touches
- `docnest/models.py::TableData` — the only type consumed (read-only).
- No edits to `reader.py`/`writer.py`/`pipeline.py` in this task (wiring is a separate gate).
