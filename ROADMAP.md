# DOCNEST Roadmap

> Living document — updated as the project evolves.
> Vote on features by reacting 👍 to the linked issue.

---

## Current Status: Alpha

Core pipeline, five-layer query engine, HTML viewer, library mode, and pluggable vector/search/storage/LLM/embedder/OCR providers are all implemented and working.

Next milestone: PyPI release (`pip install docnest-ai`) with 85%+ test coverage.

See [SPEC_DOCNEST_PYPI.md](docs/SPEC_DOCNEST_PYPI.md) for the complete technical spec.

---

## Phase 1 — Core Parser & Normalizer ✅ Done
**Shipped: v0.1.0**

- [x] `IParser` abstract base class + `ParserFactory`
- [x] `DoclingPDFParser` — PDF (text + scanned OCR via Docling)
- [x] `PyMuPDFParser` — fast fallback PDF parser
- [x] `DoclingDOCXParser` — Word documents
- [x] `ExcelParser` — XLSX with full table structure
- [x] `HTMLParser` — HTML with h1–h6 heading hierarchy
- [x] `MarkdownParser` — ATX and Setext headings
- [x] `SectionNormalizer` — assigns `§id` to every heading
- [x] Table normalization — `{ caption, headers, rows[] }` JSON
- [x] `RawDocument` and `Section` Pydantic models
- [x] CLI: `docnest convert report.pdf`
- [x] CamelCase filename normalization (`GunjanTailor.pdf` → `gunjan-tailor`)

---

## Phase 2 — Embedding + Quantization ✅ Done
**Shipped: v0.1.0 → v0.2.0**

- [x] `IEmbedder` interface
- [x] 10+ embedding providers via LangChain (HuggingFace, OpenAI, Cohere, Google, etc.)
- [x] `Quantizer` — float32 / float16 / int8 / binary
- [x] BM25 keyword index builder
- [x] `embeddings.bin` binary blob format (~87% smaller than base64)
- [x] Lazy embedding loading (matrix decoded only on first search)
- [x] Smart ZIP compression (DEFLATE-9 JSON, DEFLATE-1 binary, Store for images)
- [x] CLI: `docnest convert --embedding-model huggingface/all-MiniLM-L6-v2 --quantization float16`

---

## Phase 3 — Intelligence Engine ✅ Done
**Shipped: v0.1.0**

- [x] `IntelligenceEngine` — LLM-powered enrichment via LangChain
- [x] Section summarization (one sentence per section)
- [x] Document-level summary (three sentences)
- [x] `insights[]` extraction — 3–5 non-obvious findings
- [x] `key_numbers[]` extraction — metrics with `§citation`
- [x] Ollama local LLM support
- [x] 14+ LLM providers: OpenAI, Anthropic, Groq, Google, Ollama, Cohere, …
- [x] `--fast` mode: embeddings only, skip LLM stages
- [x] CLI: `docnest convert --llm-provider groq --llm-model llama-3.3-70b-versatile`

---

## Phase 4 — UDF Writer + Reader + Five-Layer Query ✅ Done
**Shipped: v0.1.0**

- [x] `UDFWriter` — produces `.udf` ZIP archive
- [x] `UDFReader` — loads `.udf`, five-layer query resolution
- [x] Layer 0: pre-computed answer matching (summary, insights, key_numbers)
- [x] Layer 1: BM25 + cosine hybrid search → §section navigation
- [x] Layer 2: section-scoped LLM (~300 tokens)
- [x] Layer 3: multi-section synthesis (~900 tokens)
- [x] Layer 4: full document fallback
- [x] CLI: `docnest query report.udf "What are the key risks?"`
- [x] `docnest inspect report.udf`
- [x] Pluggable vector backends: `numpy`, `faiss`, `chroma`
- [x] Pluggable search providers: `bm25`, `tfidf`, `keyword`
- [x] Pluggable storage backends: `zip`, `dir`

---

## Phase 4b — Organisational Metadata + DocMeta ✅ Done
**Shipped: v0.2.0**

- [x] `owner`, `department`, `tags`, `access_roles`, `version`, `last_updated` in `manifest.json`
- [x] CLI flags: `--owner`, `--department`, `--tags`, `--access-roles`
- [x] DocMeta surfaced in `docnest inspect` and HTML viewer

---

## Phase 7 — Library Mode ✅ Done
**Shipped: v0.3.0**

- [x] `library.json` multi-document index
- [x] `keywords_bag` pre-filter for fast cross-document search
- [x] CLI: `docnest library init / add / list / search / remove`
- [x] Cross-document BM25 pre-filter → per-document cosine re-rank

---

## Phase 7b — HTML Viewer ✅ Done
**Shipped: v0.3.0**

- [x] `docnest view <file.udf>` generates self-contained HTML
- [x] Sidebar table of contents with Intersection Observer scroll-sync
- [x] Section hierarchy, table rendering, keyword badges
- [x] Metadata bar: owner, department, model, quantization, date
- [x] `--out <file.html>` flag

---

## Phase 5 — Connectors
**Target: v0.5.0**

- [ ] `IConnector` abstract base class
- [ ] `GitHubConnector` — repos, wikis, issues, READMEs
- [ ] `ConfluenceConnector` — spaces, pages, children
- [ ] `NotionConnector` — pages, databases
- [ ] `JiraConnector` — projects, issues, epics
- [ ] `SharePointConnector` — document libraries
- [ ] CLI: `docnest sync github --repo org/repo --token $TOKEN`

---

## Phase 6 — PyPI Release
**Target: v1.0.0**

- [ ] `pip install docnest-ai`
- [ ] 85%+ test coverage
- [ ] Full type annotations + mypy passing
- [ ] API stable — semver guaranteed from 1.0.0
- [ ] Comprehensive docs site
- [ ] Example notebooks (Jupyter)
- [ ] Docker image: `ghcr.io/tailorgunjan93/docnest:latest`

---

## Phase 8 — Hierarchical Supervisor+Worker
**Target: v1.2.0**

- [ ] Auto-shard datasets > 200MB into supervisor + worker archives
- [ ] Supervisor routing via centroid cosine similarity
- [ ] `--shard-by topic | date | folder` strategies
- [ ] Reader opens `supervisor.udf` transparently
- [ ] Incremental re-indexing (only changed sections re-embedded)

---

## Ideas Under Consideration

These are not committed — open a Discussion to vote/discuss:

- [ ] PPTX parser (PowerPoint via Docling)
- [ ] EPUB parser (ebooks)
- [ ] RST parser (Sphinx docs)
- [ ] Audio transcript ingestion (Whisper → UDF)
- [ ] Azure DevOps connector
- [ ] Linear connector
- [ ] Google Drive connector
- [ ] Real-time Confluence webhook sync
- [ ] `.udf` diff — compare two versions of a document
- [ ] Qdrant / Weaviate / Pinecone vector backend plugins
- [ ] `.udf.chat` sidecar for conversation history

---

## How to Influence the Roadmap

1. **Vote** — react 👍 to issues you care about
2. **Discuss** — open a [Discussion](https://github.com/tailorgunjan93/DOCNESTd/discussions) for big ideas
3. **Build** — see [CONTRIBUTING.md](CONTRIBUTING.md) and claim an issue

The features with the most votes get prioritized next.
