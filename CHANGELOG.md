# Changelog

All notable changes to DOCNEST will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- PyPI release (`pip install docnest-ai`)
- 85%+ test coverage + mypy passing
- Docker image `ghcr.io/tailorgunjan93/docnest:latest`
- PPTX parser
- EPUB parser
- GitHub / Confluence / Notion connectors
- Hierarchical supervisor+worker sharding for datasets >200MB

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
