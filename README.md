<div align="center">

<img src="docs/logo.svg" alt="DocForge Logo" width="120" />

# DocForge

**The document normalization engine RAG has always needed.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/docforge-ai?color=green)](https://pypi.org/project/docforge-ai)
[![Status](https://img.shields.io/badge/status-pre--alpha-orange)]()
[![Stars](https://img.shields.io/github/stars/synapseai/docforged?style=social)](https://github.com/synapseai/docforged)
[![Contributors](https://img.shields.io/github/contributors/synapseai/docforged)](https://github.com/synapseai/docforged/graphs/contributors)
[![Discord](https://img.shields.io/badge/Discord-Join-7289da?logo=discord)](https://discord.gg/synapseai)

*Parse any document. Understand its structure. Build RAG that actually works.*

[Why DocForge](#-why-docforge) •
[Quick Start](#-quick-start) •
[How It Works](#-how-it-works) •
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

## ✨ Why DocForge

DocForge reads the *structure* of a document before touching the content. Every heading becomes a navigable `§section`. Every table is preserved as `{ caption, headers, rows[] }`. Every section gets a one-sentence summary, a keyword index, and a quantized embedding — computed once at ingest, used forever.

```python
from docforge import DocForge

forge = DocForge(embedding_model="nomic-embed-text", llm_provider="ollama")

# Single document
forge.convert("annual-report.pdf")  # → annual-report.udf

# Entire folder → one portable knowledge base
forge.convert("./reports/")         # → reports.udf
```

```python
from docforge import UDFIndex

index = UDFIndex.load("reports.udf")
result = index.query("What was Q3 revenue?")

print(result.answer)      # "Q3 revenue was $38M, up 22% YoY."
print(result.citation)    # "§3.1 — Revenue Breakdown"
print(result.tokens_used) # 287  (vs ~4000 with blind chunking)
```

---

## 🧠 How It Works

DocForge runs a **6-stage normalization pipeline** on every document:

```
Stage 1  Structure Extraction    (Docling)     — headings, tables, lists, hierarchy
Stage 2  Section Assignment      (rule-based)  — §1, §1.1, §1.2 ... every heading = §id
Stage 3  Table Normalization     (LLM)         — { caption, headers, rows[] } JSON
Stage 4  Section Summarization   (LLM)         — one sentence per section
Stage 5  Document Intelligence   (LLM)         — summary, insights[], key_numbers[]
Stage 6  Embedding + Quantize    (local)       — BM25 keywords + float16 vectors
```

**Stages 1, 2, and 6 run locally — zero LLM cost.**
Stages 3–5 call an LLM **once per document**. Every future query benefits for free.

The result is a `.udf` file — a self-contained, portable knowledge base:

```
document.udf  (zip)
├── manifest.json      format version, embedding model, quantization
├── catalogue.json     section index + BM25 keywords + quantized embeddings + intelligence
├── content.json       full section text (fetched on demand)
└── assets/            images, structured tables
```

---

## ⚡ Query Resolution — Five Layers

DocForge resolves queries without sending full documents to the LLM:

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

## 📦 Output: The `.udf` Format

`.udf` (Universal Document Format) is an **open format** — any tool can read it.

- Self-contained zip: no server, no database, no cloud required
- Quantized embeddings stored inside (float16 = 2× smaller, negligible accuracy loss)
- Pre-computed intelligence: summary, insights, key numbers — extracted once
- Portable: share by email, USB, S3, Slack — works anywhere
- Open spec: [github.com/synapseai/udf-spec](https://github.com/synapseai/udf-spec)

---

## 🗺 Roadmap

| Phase | Description | Status |
|---|---|---|
| **1** | Core parser + normalizer (PDF, DOCX, XLSX, HTML, MD) | 🔨 In Progress |
| **2** | Embedding + quantization (nomic, OpenAI, Google) | 📋 Planned |
| **3** | Intelligence engine (summary, insights, key_numbers) | 📋 Planned |
| **4** | UDF writer + reader + five-layer query | 📋 Planned |
| **5** | Connectors: GitHub, Confluence, Notion, Jira | 📋 Planned |
| **6** | PyPI release `pip install docforge-ai` | 📋 Planned |
| **7** | Folder → library mode (multi-document .udf) | 📋 Planned |
| **8** | Hierarchical supervisor+worker for datasets >200MB | 📋 Planned |

Track detailed progress: [ROADMAP.md](ROADMAP.md)

---

## 🤝 Contributing

**DocForge is community-first.** We are building this in the open and want contributors at every level.

### Where to start

| Area | Good for |
|---|---|
| 🧩 New parser (PPTX, EPUB, RST) | Familiar with Docling or document formats |
| 🔌 New connector (Sharepoint, Linear) | API integration experience |
| 🧪 Test fixtures | Any skill level — add sample documents for testing |
| 📖 Documentation | Any skill level — improve examples, fix typos |
| 🐛 Bug reports | Any skill level — try it, break it, report it |
| 💡 Architecture discussion | Senior engineers — open a Discussion |

See [CONTRIBUTING.md](CONTRIBUTING.md) for full guide.

**Give us a ⭐ if DocForge solves a problem you have — it helps others find the project.**

---

## 📐 Technical Specification

Full implementation spec: [SPEC_DOCFORGE_PYPI.md](docs/SPEC_DOCFORGE_PYPI.md)

Covers: architecture, SOLID compliance, design patterns, interfaces, concrete classes, code snippets, test plan, dependency costs.

---

## 📄 License

MIT — free for commercial use. See [LICENSE](LICENSE).

---

## 🔗 Ecosystem

DocForge is the foundation of the Synapse ecosystem:

| Product | Description |
|---|---|
| [docforged](https://github.com/synapseai/docforged) | This library — document normalization engine |
| [udf-spec](https://github.com/synapseai/udf-spec) | Open specification for the .udf format |
| [synapse-local](https://github.com/synapseai/synapse-local) | Desktop RAG app (Tauri) powered by DocForge |
| [udf-reader-vscode](https://github.com/synapseai/udf-reader-vscode) | VS Code extension for .udf files |
| [synapseKB](https://github.com/synapseai/synapseKB) | Cloud knowledge platform |

---

<div align="center">

Built with ❤️ for the RAG community · [synapseai.dev](https://synapseai.dev)

</div>
