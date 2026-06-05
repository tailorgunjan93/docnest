# Changelog

All notable changes to DOCNEST will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Deterministic keywords + extractive Layer 1 — zero-token answers ≥70%.**
  `docnest.keywords` populates section keywords by extraction (no LLM) so the reader's BM25
  index actually ranks sections (they were empty → hybrid search returned nothing → queries
  fell to the full-document fallback). And Layer 1 now answers with the **question-relevant
  sentence extracted from the top section** at **0 tokens** when no precomputed summary
  exists. Combined with deterministic key-numbers, the Observer's-Tax zero-token answer rate
  reached **80%** (Charter goal 70%) with per-query token cost down **92.1%** vs naive RAG;
  the Layer 0/1 deterministic answers are 100% accurate. See ADR-0009.
- **Deterministic key-number enrichment (`docnest.key_numbers`).** `key_numbers` (which power
  the Layer-0, zero-token answer path) are now extracted from text **without an LLM** — regex
  + nearest-label binding, filtering years/list-markers/identifiers — and populated by the
  pipeline by default (no-op if an LLM already filled them). Revives 0-token numeric lookups:
  on the Observer's-Tax eval the zero-token answer rate went **0% → 40%**, accuracy **90% →
  100%**, and per-query token cost **331 → 219** (54.8% under naive RAG). See ADR-0008.
- **Large-PDF foundations (passage chunking + bounded-batch embedding).**
  `docnest.chunking.chunk_text` splits oversized section prose into bounded, boundary-aware
  passages (ADR-0007) — the basis for making content deep inside huge sections (e.g. a
  100k-char appendix) retrievable instead of lost to a single truncated embedding.
  `docnest.embedder.embed_in_batches` + `UDFWriter(embed_batch_size=…)` embed in fixed-size
  batches so peak memory does not scale with document size. Both are additive building
  blocks; wiring into the retrieval path is a subsequent change.
- **PyMuPDF native table extraction.** The fast/default PDF path (`PyMuPDFParser`) now
  populates `section.tables` via `page.find_tables()` (default-on; `extract_tables=False`
  to disable). Tables are placed in reading order (attached to the heading above them) and
  their cell text is removed from prose to avoid duplication; degenerate (<2×2) candidates
  are rejected; fail-soft on any PyMuPDF error. See ADR-0006. Previously text-PDF tables
  were lost on the fast path.
- **Deterministic table aggregation (`docnest.aggregation`).** New, dependency-free,
  fail-closed module: `parse_number` (messy cells → float: `$4,050`, `12 550`, `99.97%`,
  `1.24 billion`, `5.8x`) and `TableQuery` (fuzzy column resolution, relational row filter,
  `sum`/`count`/`min`/`max`/`avg`) over `TableData`. Returns a structured
  `AggregationResult` and never guesses — unknown column / non-numeric / empty match yields
  `ok=False` + reason. Net-new and not yet wired into the query path; no `.udf`/API change.
  See ADR-0004. (36 unit tests.)
- **OCR for scanned / image PDFs (Hindi + English).**
  - `PyMuPDFParser` gains an optional **lightweight OCR** path (`ocr=True`,
    `ocr_languages`, `ocr_dpi`, `ocr_max_px`, `text_layer_min_chars`) via the
    `IOCRProvider` wrapper (EasyOCR default; graceful no-op fallback). It **skips OCR on
    pages that already have a text layer** (fast) and runs **without Docling/torch**.
    Verified on a real 1-page Hindi image PDF (500+ Devanagari chars extracted).
  - `DoclingPDFParser` gains OCR engine selection (`ocr_engine`, `ocr_lang`,
    `tesseract_cmd`, `tessdata_path`, `force_full_page_ocr`) + `_sections_from_texts`
    full-page-image text recovery — the opt-in **heavy/high-quality** option.
  - OCR is **off by default**; install `docnest-ai[ocr-easyocr]` or `[ocr-tesseract]`.

### Changed
- **Privacy (input custody):** `.udf` files now store only the source **basename** in
  `catalogue.json` by default (e.g. `report.md`) instead of the author's absolute
  filesystem path — a shared `.udf` no longer leaks username / directory layout / OS.
  URLs (connector sources) are preserved verbatim. Opt back in to the full path with
  `--include-source-path` (CLI) or `include_source_path=True`
  (`DocNestPipeline.convert` / `UDFWriter.write`). No `UDF_VERSION` change; existing
  `.udf` files load unchanged.

### Fixed
- **HTML tables now honour `rowspan` / `colspan`.** `HTMLParser` previously read `<tr>`
  cells linearly, misaligning spanned tables. Cells are now expanded into a dense
  rectangular grid (a spanning value is repeated across the cells it covers), so columns
  line up. Span-free tables are unchanged.
- **DOCX merged cells aligned (and duplicate values preserved).** `DocxParser` deduplicated
  consecutive identical cell values as a "merged cell" heuristic, which both misaligned
  `gridSpan` columns and wrongly collapsed legitimate repeated values. It now keeps
  python-docx's already-expanded grid verbatim (merged values repeated across the grid).
- **Table rows no longer truncated at query time.** The reader fed the LLM only the first
  **5 rows** of any table (`reader._get_section_text` → `rows[:5]`), causing wrong
  max/sum/lookup answers on multi-row tables. Tables are now rendered within a **character
  budget** (drop the 5-row cap), and tables survive the prose cap in both single-section
  (Layer 2) and multi-section (Layer 3) synthesis. If rows are dropped, an explicit
  `… (+N more rows)` note is appended. See ADR-0003. (Reader query path only; no `.udf`/
  format change.)

### Planned
- **Multi-aspect query decomposition** — split multi-faceted questions into aspect
  sub-queries + per-aspect retrieval (fixes the one recall miss found in the eval audit).
- JSON / JSONL parser
- PPTX parser
- EPUB parser
- 85%+ test coverage + mypy passing
- Docker image `ghcr.io/tailorgunjan93/docnest:latest`

---

## [0.6.0] — 2026-05-23

### Added — `docnest/retrieval.py` (HybridRetriever — SQLite FTS5 + Dense ANN + Section Graph)

New standalone retrieval module replacing the previous in-memory BM25 + TF-IDF approach.

**Architecture:**
- **SQLite FTS5** — built-in BM25 ranking via SQLite's FTS5 extension. Uses Porter stemmer tokeniser. ~0.5 ms per query vs ~30 ms in-memory. No extra dependencies (`sqlite3` is stdlib).
- **Dense ANN (numpy cosine)** — section embeddings stored as BLOB in SQLite, loaded lazily. ~0.1 ms per query vs ~15 ms previously.
- **Section Graph** — structural edges (parent → child, sibling → sibling) + semantic edges (cosine > 0.68). Graph expansion adds 1-hop neighbours after RRF fusion, catching adjacent sections that contain part of the answer.
- **RRF Fusion** — Reciprocal Rank Fusion (`score = Σ w_i / (60 + rank_i)`) combines BM25 and dense signals with configurable weights.

**Performance (warm cache):**

| Step | Before | After |
|---|---|---|
| BM25 index build | ~80 ms (every run) | **0 ms** (SQLite, persisted) |
| Dense embed build | ~200 ms (every run) | **0 ms** (stored in SQLite) |
| BM25 query | ~30 ms | **0.5 ms** (FTS5 C-level) |
| Dense ANN query | ~15 ms | **0.1 ms** (numpy on stored BLOB) |
| Graph expansion | 0 ms (no graph) | **0.2 ms** |
| **Total per query** | **~785 ms** | **~1 ms** |

Cold start (first build): ~250 ms (embed N sections, build FTS5 + graph once).

**Cache invalidation:** SHA-256 of `(doc_id + section_count + Σ text[:200])`. Any structural change → full rebuild.

**SQLite schema:**
```sql
CREATE VIRTUAL TABLE fts_sections USING fts5(doc_id UNINDEXED, sec_idx UNINDEXED,
    sec_id UNINDEXED, title, text, tokenize='porter ascii');

CREATE TABLE embeddings (doc_id TEXT, sec_idx INTEGER, vec BLOB, PRIMARY KEY(doc_id, sec_idx));

CREATE TABLE graph_edges (doc_id TEXT, from_idx INTEGER, to_idx INTEGER,
    edge_type TEXT, weight REAL);

CREATE TABLE doc_hashes (doc_id TEXT PRIMARY KEY, hash TEXT, n_secs INTEGER, built_at REAL);
```

### Added — Eval Engine (eval/rag_accuracy_eval.py)

- **Cerebras API support** — `--model cerebras/<model>` — OpenAI-compatible endpoint, no daily token limit
- **`--no-reranker` flag** — skip cross-encoder for speed-critical runs
- **Eager cross-encoder load** — pre-loads `ms-marco-MiniLM-L-6-v2` at startup instead of on first query (fixes ~30-min hang on cold start). Reports load time: `ready in 11s`
- **HybridRetriever integration** — eval now uses `HybridRetriever` (SQLite FTS5 + dense + graph) instead of in-memory BM25

### Added — Eval Tooling

- `run_eval.ps1` — PowerShell runner for full Gemini + Groq + judge pipeline (ASCII-safe for PS 5.1)
- `eval/_precache.py` — pre-cache PDF documents as `.pkl` files to skip re-parsing on repeat runs
- `eval/judge_answers.py` — standalone judge script for scoring saved `answers_for_claude.json` files

### Changed — pyproject.toml

- Version bumped from `0.5.0` → `0.6.0`
- Repository and issue tracker URLs corrected to `github.com/tailorgunjan93/docnest`

### Results — v7 Benchmark (Cerebras qwen-3-235b-a22b-instruct-2507)

88 questions · 10 documents · 5 formats · honest factual scoring:
- **9.55 / 10** average · **95.5%** pass rate (84/88)
- 4 real retrieval errors, zero LLM hallucinations
- DOCX, HTML, MD, and 5 PDFs score 10.0 / 10

---

## [0.5.0] — 2026-05-20

### Added
- **`CSVParser`**: parses `.csv` and `.tsv` files into a structured `RawDocument` —
  first row → column headers, remaining rows → `TableData`; delimiter auto-detected
  (comma, tab, semicolon, pipe); encoding cascade (UTF-8 BOM-safe → UTF-8 → latin-1);
  row lengths normalised (pad / truncate); registered in `ParserFactory` by default.
  Zero new dependencies (stdlib `csv` module). 60 new tests (652 total).

---

## [0.4.2] — 2026-05-19

### Fixed
- **`ExcelParser`**: single-column sheets (where every row has exactly one
  non-empty cell) were incorrectly discarded with "no data sheets" after the
  0.4.0 merged-cell fix. The pre-scan now only skips leading single-cell rows
  when a multi-column row follows them; purely single-column sheets fall back
  to using the first row as the header with no skipping.
- EPUB parser
- GitHub / Confluence / Notion connectors
- Hierarchical supervisor+worker sharding for datasets >200MB

---

## [0.4.0] — 2026-05-19

### Added
- **Multi-format RAG accuracy evaluation** (`eval/rag_accuracy_eval.py`): 38 questions
  across 7 real-world documents in 5 formats, judged by Gemini 2.5 Pro — overall **8.9/10
  average, 89% pass rate**. All structured formats (XLSX, DOCX, HTML, MD) score ≥ 9.2/10
  with 100% pass rate.

### Fixed
- **`ExcelParser`**: merged-cell title rows (e.g. `A1:F1` header spanning all columns)
  are now skipped when detecting the real column-header row. Previously this caused every
  table to appear as a single-column table, losing all numeric cell values.
- **`ExcelParser._table_text_summary`**: includes ALL data rows (previously capped at 5),
  ensuring BM25 retrieval can find sections by their numeric content.

### Stability
- Promoted from beta (`0.4.0b3`) to stable after full multi-format evaluation passing the
  8.5/10 accuracy threshold across all structured document formats.

---

## [0.4.0b3] — 2026-05-19

### Fixed
- `UDFWriter.write()`: no longer crashes when `embedder=None`; `_build_embedding_blob`,
  `_build_manifest`, and `_build_catalogue` all guard against a missing embedder —
  embedding fields default to `""` / `0` / empty blob so structure-only UDF export works
  without any LLM provider configured

---

## [0.4.0b2] — 2026-05-19

### Fixed
- `HTMLParser`: fully implemented using BeautifulSoup — walks h1–h6 headings,
  extracts body text and `<table>` elements as `TableData` objects
- `Section.section_id`: added as a property alias for `Section.id` to prevent
  `AttributeError` in external tooling that expects `.section_id`
- `UDFWriter`: `embedder` and `quantizer` are now optional constructor args;
  writer can be instantiated without an LLM provider for structure-only export

---

## [0.4.0b1] — 2026-05-19

### Fixed
- `ExcelParser` (PR #6 — jlaportebot): row-length normalisation for `openpyxl` read-only mode
  on Linux (variable-length rows padded/truncated to header width); multi-table detection per
  sheet; clear `ParseError` raised for legacy `.xls` files; `Section` constructed with
  `tables=` kwarg instead of post-construction assignment
- `scikit-learn>=1.3` added to `[dev]` extras — `TFIDFSearchProvider` tests were failing on CI
  (Linux) because the package was not installed in the test environment

### Added
- GitHub Actions issue-labeler bot: keyword → label mapping + tailored first-response comment
- GitHub Actions welcome bot: first-time contributor detection + PR checklist
- GitHub Actions stale bot: nudge at 45 days, close at 52 days, PRs exempt
- Blog section in README linking to first dev.to post

---

## [0.4.0] — 2026-05-17

### Added — Pluggable Vector Backends
- `IVectorBackend` abstract interface (`build`, `search`, `is_available`, `is_ready`)
- `NumpyVectorBackend` — default, zero extra deps; pre-normalised unit matrix; `unit_mat @ unit_q` cosine similarity
- `FAISSVectorBackend` — `IndexFlatIP` with L2 normalisation; optional `save()`/`load()` for index persistence; requires `faiss-cpu`
- `ChromaVectorBackend` — ephemeral or `PersistentClient`; `where=` metadata filter support; requires `chromadb`
- `get_vector_backend(name, **kwargs)` factory function
- `UDFReader.load()` now accepts `vector="numpy"|"faiss"|"chroma"` or a pre-built `IVectorBackend` instance
- `docnest.providers` exports all three backends + factory

### Fixed
- ChromaDB rejected empty metadata dicts (`{}`); replaced with harmless `{"_": "1"}` placeholder
- `IVectorBackend.build()` failure now falls back to `NumpyVectorBackend` automatically

---

## [0.3.0] — 2026-05-16

### Added — Library Layer
- `library.json` multi-document index for cross-document search
- `keywords_bag` field on each library entry for fast pre-filter without opening each archive
- CLI: `docnest library init / add / list / search / remove`
- Cross-document hybrid search: BM25 pre-filter → per-document cosine re-rank

### Added — HTML Viewer
- `docnest view <file.udf>` generates a self-contained single-file HTML page
- Sidebar table of contents with Intersection Observer scroll-sync
- Section heading hierarchy, table rendering, keyword badges
- Metadata bar: owner, department, model, quantization, date
- `--out <file.html>` flag to save without opening browser

---

## [0.2.0] — 2026-05-14

### Added — Binary Embeddings (`embeddings.bin`)
- `embeddings.bin` flat float16 binary blob format — ~87% smaller `catalogue.json` vs base64
- `manifest.json` gets `embedding_format: "binary"` flag when binary blob is written
- Lazy embedding loading: matrix decoded only when a search is triggered
- Smart ZIP compression: DEFLATE-9 for JSON, DEFLATE-1 for binary, ZIP_STORED for images
- Backward-compatible: auto-detects binary vs base64 format at read time

### Added — Organisational Metadata (DocMeta)
- `manifest.json` gains: `owner`, `department`, `tags`, `access_roles`, `version`, `last_updated`
- CLI flags: `--owner`, `--department`, `--tags`, `--access-roles`
- DocMeta fields surfaced in `docnest inspect` and HTML viewer metadata bar

### Added — Provider Interfaces
- `ILLMProvider` + `LangChainLLMProvider` — 14+ LLM providers via LangChain
- `IEmbedder` — 10+ embedding providers via LangChain (HuggingFace, OpenAI, Cohere, etc.)
- `ISearchProvider` — `BM25SearchProvider`, `TFIDFSearchProvider`, `KeywordSearchProvider`
- `IStorageBackend` — `ZipStorageBackend` (default), `DirectoryStorageBackend` (debug)
- `IOCRProvider` — `NullOCRProvider`, `TesseractOCRProvider`, `EasyOCRProvider`
- All providers exported from `docnest.providers`

---

## [0.1.0] — 2026-05-10

### Added — Core Pipeline
- `IParser` abstract base class + `ParserFactory`
- `DoclingPDFParser` — PDF text + scanned pages (Docling backend)
- `PyMuPDFParser` — fast fallback PDF parser (PyMuPDF backend)
- `DoclingDOCXParser` — Word documents
- `ExcelParser` — XLSX; each sheet → sections, all tables preserved
- `HTMLParser` — h1–h6 hierarchy via BeautifulSoup
- `MarkdownParser` — ATX and Setext headings via mistletoe
- `SectionNormalizer` — assigns `§id` hierarchy to every heading
- Table normalization to `{ caption, headers, rows[] }` JSON
- `RawDocument` and `Section` Pydantic models
- `UDFWriter` — produces `.udf` ZIP archive (`manifest.json`, `catalogue.json`, `content.json`)
- `UDFReader` — loads `.udf`, five-layer query resolution (L0–L4)
  - L0: pre-computed summary / insights / key_numbers
  - L1: BM25 + cosine hybrid → §section navigation
  - L2: section-scoped LLM (~300 tokens)
  - L3: multi-section synthesis (~900 tokens)
  - L4: full-document fallback
- `IntelligenceEngine` — LLM-powered: section summaries, document summary, insights, key_numbers
- `Quantizer` — float32, float16, int8, binary quantization
- CLI: `docnest convert`, `docnest query`, `docnest inspect`
- CamelCase filename normalization: `GunjanTailor.pdf` → `doc_id: "gunjan-tailor"`, `title: "Gunjan Tailor"`
- `.gitignore` entries for generated archives, HTML viewer output, temp scripts

### Fixed
- `_filename_to_title` in both PDF parsers: CamelCase stems now split correctly on word boundaries
- `_make_doc_id` in `parsers/base.py`: handles CamelCase, digit transitions, and mixed separators

---

## How Versions Work

| Version range | Meaning |
|---|---|
| 0.x.y | Pre-release — API may change |
| 1.0.0 | Stable — API semver guaranteed |
| 1.x.y | Backward compatible additions |
| 2.0.0 | Breaking changes — migration guide provided |
