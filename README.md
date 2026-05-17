<div align="center">

<img src="docs/logo.svg" alt="DOCNEST Logo" width="120" />

# DOCNEST

**The document normalization engine RAG has always needed.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/docnest-ai?color=green)](https://pypi.org/project/docnest-ai)
[![Status](https://img.shields.io/badge/status-alpha-yellow)]()
[![Stars](https://img.shields.io/github/stars/tailorgunjan93/DOCNESTd?style=social)](https://github.com/tailorgunjan93/DOCNESTd)
[![Contributors](https://img.shields.io/github/contributors/tailorgunjan93/DOCNESTd)](https://github.com/tailorgunjan93/DOCNESTd/graphs/contributors)

*Parse any document. Understand its structure. Build RAG that actually works.*

[Why DOCNEST](#-why-docnest) •
[Quick Start](#-quick-start) •
[How It Works](#-how-it-works) •
[CLI Reference](#-cli-reference) •
[Roadmap](#-roadmap) •
[Contributing](#-contributing)

</div>

---

## The Problem with RAG Today

Every RAG pipeline ingests documents the same broken way:

```
PDF → extract text → split every 512 chars → embed → store → hope
```

What gets silently destroyed:

| Source | What blind chunking loses |
|---|---|
| Financial report | Table row `45.2% \| Q3 \| Europe` has no column headers |
| Legal contract | Clause split mid-sentence across two chunks |
| API documentation | Code example separated from its description |
| Research paper | Figure caption disconnected from its analysis |

**The LLM receives noise and returns approximate answers.** This is not a retrieval problem — it is an ingestion problem.

---

## ✨ Why DOCNEST

DOCNEST reads the *structure* of a document before touching the content. Every heading becomes a navigable `§section`. Every table is preserved as `{ caption, headers, rows[] }`. Every section gets a one-sentence summary, a keyword index, and a quantized embedding — computed once at ingest, used forever.

The output is a `.udf` file — a self-contained portable knowledge base you can share by email, copy to USB, or upload to S3.

---

## 🚀 Quick Start

```bash
pip install docnest-ai
```

### Convert a document

```bash
# Basic convert (local embeddings, no LLM)
docnest convert report.pdf

# With LLM intelligence enrichment
docnest convert report.pdf --llm-provider groq --llm-model llama-3.3-70b-versatile

# Fast mode: embeddings only, skip LLM stages
docnest convert report.pdf --fast

# With organizational metadata
docnest convert report.pdf \
  --owner "Alice Smith" \
  --department "Finance" \
  --tags "q4,2024,revenue"
```

### Query a document

```bash
docnest query report.udf "What was Q3 revenue?"
docnest query report.udf "What are the key risks?" --layers 0,1,2
```

### Inspect a document

```bash
docnest inspect report.udf
```

### View as HTML

```bash
docnest view report.udf          # opens in browser
docnest view report.udf --out report.html
```

### Library (multi-document search)

```bash
docnest library init ./docs/
docnest library add  ./docs/ report.udf
docnest library add  ./docs/ contract.udf
docnest library list ./docs/
docnest library search ./docs/ "revenue forecast"
docnest library remove ./docs/ old-report.udf
```

---

## Python API

```python
from docnest import DocNestPipeline

# Convert with all defaults (HuggingFace embeddings, no LLM)
pipeline = DocNestPipeline()
pipeline.convert("report.pdf")   # → report.udf

# With LLM + custom embedding model
pipeline = DocNestPipeline(
    embedding_model="huggingface/all-MiniLM-L6-v2",
    llm_provider="groq",
    llm_model="llama-3.3-70b-versatile",
    api_key="gsk_...",
)
pipeline.convert("report.pdf")
```

```python
from docnest import UDFReader

reader = UDFReader.load("report.udf")

# Simple query
result = reader.query("What was Q3 revenue?")
print(result["answer"])     # "Q3 revenue was $38M, up 22% YoY."
print(result["citation"])   # "§3.1 — Revenue Breakdown"

# Use a specific vector backend
reader = UDFReader.load("report.udf", vector="faiss")
reader = UDFReader.load("report.udf", vector="chroma", persist_directory="./chroma_db")
```

### Pluggable vector backends

| Backend | Install | Best for |
|---|---|---|
| `numpy` (default) | built-in | Small docs, zero extra deps |
| `faiss` | `pip install faiss-cpu` | Fast ANN on large docs |
| `chroma` | `pip install chromadb` | Persistent cross-session store |

```python
from docnest.providers import get_vector_backend

backend = get_vector_backend("faiss")
reader = UDFReader.load("report.udf", vector=backend)
```

---

## 🧠 How It Works

DOCNEST runs a **6-stage normalization pipeline** on every document:

```
Stage 1  Structure Extraction    (Docling / PyMuPDF)  — headings, tables, lists, hierarchy
Stage 2  Section Assignment      (rule-based)          — §1, §1.1, §1.2 ... every heading = §id
Stage 3  Table Normalization     (LLM)                 — { caption, headers, rows[] } JSON
Stage 4  Section Summarization   (LLM)                 — one sentence per section
Stage 5  Document Intelligence   (LLM)                 — summary, insights[], key_numbers[]
Stage 6  Embedding + Quantize    (local)               — BM25 keywords + float16 vectors
```

**Stages 1, 2, and 6 run locally — zero LLM cost.**
Stages 3–5 call an LLM **once per document**. Every future query benefits for free.

The result is a `.udf` file — a self-contained, portable knowledge base:

```
document.udf  (zip)
├── manifest.json      format version, embedding model, quantization, DocMeta
├── catalogue.json     section index + BM25 keywords + intelligence
├── content.json       full section text (loaded on demand)
├── embeddings.bin     flat float16 binary blob (~87% smaller than base64)
└── assets/            images, structured tables
```

> **`embeddings.bin`** is a flat binary blob: `N × D × 2 bytes` (float16).
> The old base64-per-section format is still read for backward compatibility.

---

## ⚡ Query Resolution — Five Layers

DOCNEST resolves queries without sending full documents to the LLM:

| Layer | Mechanism | Tokens | Latency |
|---|---|---|---|
| 0 | Pre-computed (summary, insights, key_numbers) | **0** | < 1ms |
| 1 | BM25 + cosine → navigate to §section | **0** | < 20ms |
| 2 | Section-scoped LLM (~300 tokens) | ~300 | 1–3s |
| 3 | Multi-section synthesis (~900 tokens) | ~900 | 2–5s |
| 4 | Full document fallback | ~4000+ | 5–15s |
| — | Naive RAG (blind chunking) | ~4000–8000 | 5–15s |

**Layer 0 and 1 answer ~70% of real-world questions with zero LLM cost.**

---

## 📦 Supported Formats

| Format | Parser | Notes |
|---|---|---|
| PDF (text) | Docling | Full heading hierarchy, table extraction |
| PDF (scanned) | Docling + Tesseract OCR | OCR fallback per page |
| DOCX | Docling | Word documents with styles |
| XLSX | OpenPyXL | Each sheet → sections, all tables preserved |
| HTML | BeautifulSoup | h1-h6 hierarchy |
| Markdown | mistletoe | ATX and Setext headings |

---

## 🔌 Provider Interfaces

All external dependencies sit behind swappable interfaces. Change the backend string — no other code changes required.

| Interface | Options | Notes |
|---|---|---|
| `ILLMProvider` | `groq`, `openai`, `ollama`, `anthropic`, … | 14+ via LangChain |
| `IEmbedder` | `huggingface`, `openai`, `cohere`, … | 10+ via LangChain |
| `IVectorBackend` | `numpy`, `faiss`, `chroma` | Pluggable similarity search |
| `ISearchProvider` | `bm25`, `tfidf`, `keyword` | Keyword/hybrid search |
| `IStorageBackend` | `zip` (default), `dir` | Archive read/write |
| `IOCRProvider` | `null`, `tesseract`, `easyocr` | OCR for scanned pages |

---

## 🗺 Roadmap

| Phase | Description | Status |
|---|---|---|
| **1** | Core parser + normalizer (PDF, DOCX, XLSX, HTML, MD) | ✅ Done |
| **2** | Embedding + quantization (10+ models via LangChain) | ✅ Done |
| **3** | Intelligence engine (summary, insights, key_numbers) | ✅ Done |
| **4** | UDF writer + reader + five-layer query | ✅ Done |
| **5** | Connectors: GitHub, Confluence, Notion, Jira | 📋 Planned |
| **6** | PyPI release `pip install docnest-ai` | 🔨 In Progress |
| **7** | Library mode (multi-document cross-search) | ✅ Done |
| **8** | Hierarchical supervisor+worker for datasets >200MB | 📋 Planned |

Track detailed progress: [ROADMAP.md](ROADMAP.md)

---

## 🤝 Contributing

**DOCNEST is community-first.** We are building this in the open and want contributors at every level.

### Where to start

| Area | Good for |
|---|---|
| 🧩 New parser (PPTX, EPUB, RST) | Familiar with Docling or document formats |
| 🔌 New vector backend (Qdrant, Weaviate) | Vector database experience |
| 🔌 New connector (SharePoint, Linear) | API integration experience |
| 🧪 Test fixtures | Any skill level — add sample documents for testing |
| 📖 Documentation | Any skill level — improve examples, fix typos |
| 🐛 Bug reports | Any skill level — try it, break it, report it |
| 💡 Architecture discussion | Senior engineers — open a Discussion |

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

**Give us a ⭐ if DOCNEST solves a problem you have — it helps others find the project.**

---

## 📐 Technical Specification

Full implementation spec: [SPEC_DOCNEST_PYPI.md](docs/SPEC_DOCNEST_PYPI.md)

Covers: architecture, SOLID compliance, design patterns, interfaces, concrete classes, code snippets, test plan, dependency costs.

Open format spec: [github.com/tailorgunjan93/udf-spec](https://github.com/tailorgunjan93/udf-spec)

---

## 📄 License

MIT — free for commercial use. See [LICENSE](LICENSE).

---

## 🔗 Ecosystem

| Product | Description |
|---|---|
| [DOCNESTd](https://github.com/tailorgunjan93/DOCNESTd) | This library — document normalization engine |
| [udf-spec](https://github.com/tailorgunjan93/udf-spec) | Open specification for the `.udf` format |
| [synapse-local](https://github.com/tailorgunjan93/synapse-local) | Desktop RAG app (Tauri) powered by DOCNEST |
| [udf-reader-vscode](https://github.com/tailorgunjan93/udf-reader-vscode) | VS Code extension for `.udf` files |

---

<div align="center">

Built with ❤️ for the RAG community · [github.com/tailorgunjan93/DOCNESTd](https://github.com/tailorgunjan93/DOCNESTd)

</div>
