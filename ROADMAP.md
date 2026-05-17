# DocForge Roadmap

> Living document — updated as the project evolves.
> Vote on features by reacting 👍 to the linked issue.

---

## Current Status: Pre-Alpha

The architecture is fully designed. Implementation starts now.
See [SPEC_DOCFORGE_PYPI.md](docs/SPEC_DOCFORGE_PYPI.md) for the complete technical spec.

---

## Phase 1 — Core Parser & Normalizer
**Target: v0.1.0**

- [ ] `IParser` abstract base class + `ParserFactory`
- [ ] `DoclingPDFParser` — PDF (text + scanned OCR)
- [ ] `DoclingDOCXParser` — Word documents
- [ ] `ExcelParser` — XLSX with full table structure
- [ ] `HTMLParser` — HTML with heading hierarchy
- [ ] `MarkdownParser` — Markdown
- [ ] `SectionNormalizer` — assigns `§id` to every heading
- [ ] Table normalization — `{ caption, headers, rows[] }` JSON
- [ ] `RawDocument` and `Section` Pydantic models
- [ ] CLI: `docforge convert report.pdf`

---

## Phase 2 — Embedding + Quantization
**Target: v0.2.0**

- [ ] `IEmbedder` interface
- [ ] `NomicEmbedder` — `nomic-embed-text` via fastembed (local, free)
- [ ] `OpenAIEmbedder` — `text-embedding-3-small`
- [ ] `GoogleEmbedder` — `text-embedding-004`
- [ ] `Quantizer` — float32 / float16 / int8 / binary
- [ ] BM25 keyword index builder (`rank-bm25`)
- [ ] CLI: `docforge convert --embedding-model nomic-embed-text --quantization float16`

---

## Phase 3 — Intelligence Engine
**Target: v0.3.0**

- [ ] `IntelligenceEngine` — LLM-powered enrichment via LiteLLM
- [ ] Section summarization (one sentence per section)
- [ ] Document-level summary (three sentences)
- [ ] `insights[]` extraction — 3-5 non-obvious findings
- [ ] `key_numbers[]` extraction — metrics with `§citation`
- [ ] Ollama local LLM support
- [ ] OpenAI / Anthropic / Groq / Google support
- [ ] CLI: `docforge convert --llm-provider ollama --llm-model llama3.2`

---

## Phase 4 — UDF Writer + Reader + Five-Layer Query
**Target: v0.4.0**

- [ ] `UDFWriter` — produces `.udf` zip file
- [ ] `UDFIndex` — loads `.udf`, five-layer query resolution
- [ ] Layer 0: pre-computed answer matching
- [ ] Layer 1: BM25 + cosine hybrid search
- [ ] Layer 2: section-scoped LLM
- [ ] Layer 3: multi-section synthesis
- [ ] Layer 4: full document fallback
- [ ] CLI: `docforge query report.udf "What are the key risks?"`
- [ ] `.udf.chat` sidecar read/write

---

## Phase 5 — Connectors
**Target: v0.5.0**

- [ ] `IConnector` abstract base class
- [ ] `GitHubConnector` — repos, wikis, issues, READMEs
- [ ] `ConfluenceConnector` — spaces, pages, children
- [ ] `NotionConnector` — pages, databases
- [ ] `JiraConnector` — projects, issues, epics
- [ ] CLI: `docforge sync github --repo org/repo --token $TOKEN`

---

## Phase 6 — PyPI Release
**Target: v1.0.0**

- [ ] `pip install docforge-ai`
- [ ] 85%+ test coverage
- [ ] Full type annotations + mypy passing
- [ ] API stable — semver guaranteed from 1.0.0
- [ ] Comprehensive docs at docs.docforge.dev
- [ ] Example notebooks (Jupyter)
- [ ] Docker image: `ghcr.io/synapseai/docforge:latest`

---

## Phase 7 — Library Mode (Folder → Single .udf)
**Target: v1.1.0**

- [ ] `docforge convert ./folder/ --output library.udf`
- [ ] `library_catalogue.json` unified cross-document index
- [ ] Worker centroid embeddings for hierarchical routing
- [ ] 200MB size guard with `--split` auto-sharding
- [ ] Cross-document query resolution

---

## Phase 8 — Hierarchical Supervisor+Worker
**Target: v1.2.0**

- [ ] Auto-shard datasets > 200MB into supervisor + workers
- [ ] Supervisor routing via centroid cosine similarity
- [ ] `--shard-by topic | date | folder` strategies
- [ ] Reader opens supervisor.udf transparently

---

## Ideas Under Consideration

These are not committed — open a Discussion to vote/discuss:

- [ ] PPTX parser (PowerPoint)
- [ ] EPUB parser (ebooks)
- [ ] RST parser (Sphinx docs)
- [ ] Audio transcript ingestion (Whisper)
- [ ] Azure DevOps connector
- [ ] Linear connector
- [ ] Google Drive connector
- [ ] Real-time Confluence webhook sync
- [ ] Incremental re-indexing (only changed sections re-embedded)
- [ ] `.udf` diff — compare two versions of a document

---

## How to Influence the Roadmap

1. **Vote** — react 👍 to issues you care about
2. **Discuss** — open a [Discussion](https://github.com/synapseai/docforged/discussions) for big ideas
3. **Build** — see [CONTRIBUTING.md](CONTRIBUTING.md) and claim an issue

The features with the most votes get prioritized next.
