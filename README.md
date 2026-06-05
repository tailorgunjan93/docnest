<div align="center">

<img src="docs/logo.svg" alt="DOCNEST Logo" width="100" />

# DOCNEST

**Secure · Fast · Reliable · Cost-Effective**

*The document normalization engine RAG has always needed.*

[![CI](https://github.com/tailorgunjan93/docnest/actions/workflows/ci.yml/badge.svg)](https://github.com/tailorgunjan93/docnest/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/docnest-ai?color=green)](https://pypi.org/project/docnest-ai)
[![PyPI Downloads](https://img.shields.io/pypi/dm/docnest-ai?color=blue)](https://pypi.org/project/docnest-ai)
[![Accuracy](https://img.shields.io/badge/RAG%20Accuracy-8.5%2F10-brightgreen)](https://github.com/tailorgunjan93/docnest#-accuracy-benchmark--multi-format-rag-evaluation)
[![Status](https://img.shields.io/badge/status-stable-brightgreen)]()
[![Stars](https://img.shields.io/github/stars/tailorgunjan93/docnest?style=social)](https://github.com/tailorgunjan93/docnest)
[![Contributors](https://img.shields.io/github/contributors/tailorgunjan93/docnest)](https://github.com/tailorgunjan93/docnest/graphs/contributors)

<img src="docs/banner.svg" alt="DOCNEST Banner" width="100%" />

[Why DOCNEST](#-why-docnest) •
[Installation](#-installation) •
[Quick Start](#-quick-start) •
[Python API](#-python-api) •
[PDF Parsing](#-pdf-parsing--memory-guide) •
[How It Works](#-how-it-works) •
[Benchmark](#-accuracy-benchmark--multi-format-rag-evaluation) •
[Providers](#-provider-interfaces) •
[Roadmap](#-roadmap)

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

### See the difference

Take a financial report with a revenue table. Here is what each approach gives your LLM:

**❌ Blind chunking (LangChain / LlamaIndex default)**
```
chunk_1: "45.2%  Q3  Europe  38.1%  Q2  Europe  41.7%  Q3"
chunk_2: "Asia   29.3%  Q2  Asia  Americas  52.1%  Q3  Ame"
```
The LLM has numbers. It has no idea what they mean.

**✅ DOCNEST**
```json
{
  "section": "§4.2 Revenue by Region",
  "table": {
    "caption": "Quarterly revenue breakdown by region",
    "headers": ["Region", "Q2 Revenue", "Q3 Revenue", "Change"],
    "rows": [
      ["Europe",   "38.1%", "45.2%", "+7.1pp"],
      ["Asia",     "29.3%", "41.7%", "+12.4pp"],
      ["Americas", "n/a",   "52.1%", "—"]
    ]
  },
  "summary": "Q3 revenue grew across all regions, led by Asia (+12.4pp)."
}
```
The LLM knows exactly what the numbers mean, where they came from, and how they relate.

---

## ✨ Why DOCNEST

DOCNEST reads the *structure* of a document before touching the content. Every heading becomes a navigable `§section`. Every table is preserved as `{ caption, headers, rows[] }`. Every section gets a one-sentence summary, a keyword index, and a quantized embedding — computed once at ingest, used forever.

The output is a `.udf` file — a self-contained portable knowledge base you can share by email, copy to USB, or upload to S3.

### New in 0.7.0
- **Zero-token answers (deterministic intelligence).** `key_numbers` and section `keywords`
  are now extracted **without an LLM** (regex + ranking), so factual lookups are answered
  from precomputed data at **0 tokens** — on the in-house benchmark this took the
  zero-token answer rate from 0% → **80%** on factual queries, **100% accurate**, ~**92%**
  fewer tokens than naive RAG. (An LLM is still optional for summaries/synthesis.)
- **Deterministic table aggregation** (`docnest.aggregation`) — exact `sum`/`count`/`min`/
  `max`/`avg` over a table column, fail-closed, no LLM.
- **Better tables** — native PyMuPDF table extraction (fast PDF path), HTML `rowspan`/
  `colspan`, DOCX merged cells, budgeted full-table rendering in the query path.
- **Scanned/image PDFs** — lightweight OCR (Hindi + English) on the fast path.
- **Large PDFs** — passage chunking + bounded-batch embedding (bounded memory).

---

## ⚡ Try it in 60 seconds

```bash
pip install docnest-ai pymupdf
```

```python
from docnest.parsers.pymupdf_pdf import PyMuPDFParser
from docnest.normalizer import SectionNormaliser
from docnest.writer import UDFWriter
from docnest.reader import UDFIndex

# Parse → normalise → save (no LLM, no API key needed)
raw = PyMuPDFParser().parse("your-document.pdf")
doc = SectionNormaliser().normalise(raw)
UDFWriter().write(doc, "my-doc.udf")

# Query
idx = UDFIndex.load("my-doc.udf")
result = idx.query(
    "What was Q3 revenue?",
    llm_provider="groq",
    llm_model="llama-3.3-70b-versatile",
    llm_api_key="gsk_...",   # free at console.groq.com
)
print(result.answer)      # "Q3 revenue was $38M, up 22% YoY."
print(result.layer_used)  # 1 — answered from index, 0 LLM tokens
```

---

## 📦 Installation

```bash
pip install docnest-ai
```

### Optional extras

```bash
# Fast PDF parsing (no ML, no downloads) — recommended for most PDFs
pip install pymupdf

# ML-quality PDF parsing (tables, scanned docs) — requires more RAM
pip install docling

# Fast approximate nearest-neighbour search (large document sets)
pip install faiss-cpu

# Persistent cross-session vector store
pip install chromadb

# Everything at once
pip install docnest-ai pymupdf docling faiss-cpu chromadb
```

---

## 🚀 Quick Start

### Convert a document

```bash
# Fastest — PyMuPDF parser, local embeddings, no LLM required
docnest convert report.pdf --pdf-engine pymupdf --fast

# Full quality — Docling parser + LLM enrichment (Groq is free-tier friendly)
docnest convert report.pdf --llm-provider groq --llm-model llama-3.3-70b-versatile

# Large PDF (>30 pages) — auto page-chunked, full ML quality, bounded RAM
docnest convert big-report.pdf --llm-provider openai --llm-model gpt-4o-mini

# With metadata tags
docnest convert report.pdf \
  --owner "Alice Smith" \
  --department "Finance" \
  --tags "q4,2024,revenue"

# Privacy: by default the .udf stores only the source basename (e.g. report.pdf),
# never your absolute path. Pass --include-source-path to keep the full path.
docnest convert report.pdf --include-source-path
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
docnest view report.udf           # opens browser
docnest view report.udf --out report.html
```

### Library — multi-document search

```bash
docnest library init ./docs/
docnest library add  ./docs/ report.udf
docnest library add  ./docs/ contract.udf
docnest library list ./docs/
docnest library search ./docs/ "revenue forecast"
docnest library remove ./docs/ old-report.udf
```

---

## 🐍 Python API

### Converting a document

```python
from docnest.pipeline import DocNestPipeline

# ── Option 1: Fully local — no API keys, no internet after first download ──
pipeline = DocNestPipeline(
    llm_provider="ollama",
    llm_model="llama3.2",          # ollama pull llama3.2
    emb_provider="huggingface",
    emb_model="all-MiniLM-L6-v2",  # downloaded automatically on first run
)
pipeline.convert("report.pdf")     # → report.udf

# ── Option 2: Groq LLM + local HuggingFace embeddings (recommended) ──
pipeline = DocNestPipeline(
    llm_provider="groq",
    llm_model="llama-3.3-70b-versatile",
    llm_api_key="gsk_...",          # or set GROQ_API_KEY env var
    emb_provider="huggingface",
    emb_model="all-MiniLM-L6-v2",
)
pipeline.convert("report.pdf")

# ── Option 3: OpenAI for both LLM and embeddings ──
pipeline = DocNestPipeline(
    llm_provider="openai",
    llm_model="gpt-4o-mini",
    llm_api_key="sk-...",
    emb_provider="openai",
    emb_model="text-embedding-3-small",
    emb_api_key="sk-...",
)
pipeline.convert("report.pdf")

# ── Option 4: Skip intelligence (no LLM, fastest) ──
pipeline = DocNestPipeline(skip_intelligence=True)
pipeline.convert("report.pdf")     # embeddings only, no section summaries

# ── Option 5: Custom output path + progress callback ──
pipeline = DocNestPipeline(
    llm_provider="groq",
    llm_api_key="gsk_...",
)
pipeline.convert(
    "report.pdf",
    output_path="./output/report.udf",
    on_stage_complete=lambda stage, _: print(f"✓ {stage}"),
)
```

### Querying a document

```python
from docnest.reader import UDFIndex

# Load the .udf file (instant — no LLM needed to load)
idx = UDFIndex.load("report.udf")

# ── Simple query — escalates through layers automatically ──
result = idx.query(
    "What was Q3 revenue?",
    llm_provider="groq",
    llm_model="llama-3.3-70b-versatile",
    llm_api_key="gsk_...",
)

print(result.answer)       # "Q3 revenue was $38M, up 22% YoY."
print(result.citations)    # ["§3.1"]
print(result.layer_used)   # 1  (BM25+cosine, 0 tokens!)
print(result.tokens_used)  # 0

# ── Use FAISS for faster search on large documents ──
idx = UDFIndex.load("report.udf", vector="faiss")

# ── ChromaDB — persists across sessions ──
idx = UDFIndex.load("report.udf", vector="chroma", persist_dir="./chroma_store")

# ── Multiple queries on same index (load once, reuse) ──
questions = [
    "What were the key risks?",
    "What is the revenue forecast for 2025?",
    "Who are the main competitors?",
]
for q in questions:
    r = idx.query(q, llm_provider="groq", llm_api_key="gsk_...")
    print(f"[L{r.layer_used}] {r.answer[:120]}")
```

### Parsing PDFs directly

```python
from docnest.parsers.pdf import DoclingPDFParser
from docnest.parsers.pymupdf_pdf import PyMuPDFParser
from docnest.parsers.factory import ParserFactory

# ── DoclingPDFParser — full ML quality (tables, headings, scanned pages) ──

# Small PDF (≤30 pages) — runs Docling directly
parser = DoclingPDFParser()
raw = parser.parse("report.pdf")

# Large PDF — auto page-chunked in 30-page pieces, same full ML quality
raw = DoclingPDFParser().parse("600-page-annual-report.pdf")

# Explicit chunk size — tune to your RAM
raw = DoclingPDFParser(chunk_pages=10).parse("large.pdf")   # low RAM machine
raw = DoclingPDFParser(chunk_pages=50).parse("large.pdf")   # high RAM machine

# Scanned PDF (OCR) — requires Docling's Tesseract integration
raw = DoclingPDFParser(ocr=True).parse("scanned-contract.pdf")

# ── PyMuPDFParser — fast, zero ML, works on any machine ──
parser = PyMuPDFParser()
raw = parser.parse("report.pdf")

# ── ParserFactory — auto-selects the right parser by file extension ──
factory = ParserFactory()                          # default: Docling for PDF
factory = ParserFactory(pdf_engine="pymupdf")      # lightweight: PyMuPDF for PDF

raw = factory.get("report.pdf").parse("report.pdf")
raw = factory.get("report.docx").parse("report.docx")
raw = factory.get("data.xlsx").parse("data.xlsx")
raw = factory.get("sales.csv").parse("sales.csv")     # also .tsv
raw = factory.get("page.html").parse("page.html")
raw = factory.get("notes.md").parse("notes.md")

# Inspect what was parsed
print(f"Sections: {len(raw.sections)}")
for s in raw.sections:
    print(f"  L{s.level}  {s.title}  ({len(s.tables)} tables)")
```

### Custom PDF engine at runtime

```python
from docnest.parsers.factory import ParserFactory

factory = ParserFactory()

# Switch to PyMuPDF for this session
factory.set_pdf_engine("pymupdf")

# Switch back to Docling
factory.set_pdf_engine("docling")

# Register a completely custom parser
from docnest.parsers.base import IParser

class MyParser(IParser):
    def supports(self, path: str) -> bool:
        return path.endswith(".myformat")
    def parse(self, path: str):
        ...

factory.register(MyParser())
```

---

## 📄 PDF Parsing & Memory Guide

DOCNEST gives you two PDF parsers. Choose based on your document type and available RAM:

| | `DoclingPDFParser` | `PyMuPDFParser` |
|---|---|---|
| **Table quality** | ✅ ML-grade (TableFormer) | ✅ Native (`find_tables`, default-on) |
| **Scanned PDFs** | ✅ OCR support (heavy ML) | ✅ Lightweight OCR (opt-in) |
| **Heading detection** | ✅ Semantic (Docling layout) | ⚠️ Font-size heuristic |
| **RAM usage** | ~1–2 GB (ML models) | ~50 MB |
| **First-run download** | ~1 GB models | None |
| **Speed** | Slower | Very fast |
| **Best for** | Financial reports, contracts, research papers | Resumes, simple reports, fast prototyping |

### Memory management for large PDFs

`DoclingPDFParser` auto-chunks large PDFs — no quality loss, bounded RAM:

```python
# Auto-chunking kicks in for PDFs > 30 pages
# Peak RAM ≈ RAM_per_chunk, not RAM_for_whole_file
raw = DoclingPDFParser().parse("600-page-report.pdf")

# Tune chunk size to your machine
raw = DoclingPDFParser(chunk_pages=10).parse("report.pdf")   # 8 GB RAM
raw = DoclingPDFParser(chunk_pages=30).parse("report.pdf")   # 16 GB RAM (default)
raw = DoclingPDFParser(chunk_pages=60).parse("report.pdf")   # 32 GB+ RAM

# Page images are disabled by default (saves 50-200 MB per page)
# Only enable if you specifically need image assets
raw = DoclingPDFParser(generate_images=True).parse("report.pdf")
```

**How chunking works:**
1. PyMuPDF splits the PDF into N-page temp files
2. Docling runs with full ML quality on each chunk
3. Sections are merged — output is identical to processing the whole file at once
4. Temp files are deleted immediately after each chunk

If you hit `std::bad_alloc` or `OSError: paging file too small`, fall back to PyMuPDF:

```python
from docnest.parsers.pymupdf_pdf import PyMuPDFParser
raw = PyMuPDFParser().parse("huge.pdf")  # Zero ML, always succeeds
```

### OCR for scanned / image PDFs (Hindi + English, fast path)

`PyMuPDFParser` has an **optional lightweight OCR** path — it OCRs only image-only pages
(pages with a text layer are used as-is, so it's fast) and runs **without Docling/torch**.

```bash
pip install docnest-ai[ocr-easyocr]   # EasyOCR (Hindi, English, 80+ scripts)
#   or: pip install docnest-ai[ocr-tesseract]   # lighter, needs the Tesseract binary
```

```python
from docnest.parsers.pymupdf_pdf import PyMuPDFParser

# Scanned invitation in Hindi + English — text pages are skipped (no wasted OCR)
raw = PyMuPDFParser(ocr=True, ocr_languages=["hi", "en"]).parse("scanned.pdf")

# Tune speed vs accuracy
raw = PyMuPDFParser(ocr=True, ocr_dpi=150, ocr_max_px=1600).parse("scanned.pdf")
```

For maximum table/layout quality on scans (needs RAM/CPU/internet), use Docling's OCR:

```python
from docnest.parsers.pdf import DoclingPDFParser
raw = DoclingPDFParser(ocr=True, ocr_engine="easyocr", ocr_lang=["hi", "en"]).parse("scanned.pdf")
```

---

## 🧠 How It Works

DOCNEST runs a **6-stage normalization pipeline** on every document:

```
Stage 1  Structure Extraction    (Docling / PyMuPDF)   headings, tables, lists, hierarchy
Stage 2  Section Assignment      (rule-based)           §1, §1.1, §1.2 … every heading = §id
Stage 3  Table Normalization     (normaliser)           { caption, headers, rows[] } JSON
Stage 4  Section Keywords         (deterministic)        keyword index per section — no LLM
Stage 5  Document Intelligence   (deterministic + LLM)  key_numbers (no LLM); summary/insights (LLM, optional)
Stage 6  Embedding + Quantize    (local)                BM25 keywords + float16 vectors
```

**Stages 1, 2, 3, and 6 run locally — zero LLM cost.**  
Stages 4–5 call an LLM **once per document**. Every future query benefits for free.

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
> Legacy base64-per-section format is still read for backward compatibility.

> **🔒 Privacy by default:** `catalogue.json` stores only the source **basename**
> (e.g. `report.pdf`) — never your absolute filesystem path — so a shared `.udf` never
> leaks your username, directory layout, or OS. Pass `--include-source-path` (CLI) or
> `include_source_path=True` (`convert()` / `UDFWriter.write()`) to keep the full path.

---

## ⚡ Query Resolution — Five Layers

DOCNEST resolves queries without sending full documents to the LLM:

| Layer | Mechanism | Tokens | Latency | Cost |
|---|---|---|---|---|
| 0 | Pre-computed (summary, insights, key_numbers) | **0** | < 1 ms | **$0** |
| 1 | BM25 + cosine → navigate to §section | **0** | < 20 ms | **$0** |
| 2 | Section-scoped LLM (~300 tokens) | ~300 | 1–3 s | ~$0.0001 |
| 3 | Multi-section synthesis (~900 tokens) | ~900 | 2–5 s | ~$0.0003 |
| 4 | Full document fallback | ~4,000+ | 5–15 s | ~$0.001 |
| — | **Naive RAG (blind chunking)** | ~4,000–8,000 | 5–15 s | ~$0.001–0.002 |
| — | **Real traditional RAG (full PDF)** | ~80,000–120,000 | 5–15 s | ~$0.10–0.15 |

**Layers 0 and 1 answer ~70% of real-world questions with zero LLM cost.**  
**DocNest averages ~2,600 tokens on structured files — 67–71% fewer tokens than traditional RAG.**

---

## 📂 Supported Formats

| Format | Parser | Notes |
|---|---|---|
| PDF (text-based) | `DoclingPDFParser` / `PyMuPDFParser` | Full heading hierarchy, table extraction |
| PDF (scanned) | `DoclingPDFParser(ocr=True)` | OCR via Docling's Tesseract integration |
| DOCX | `DocxParser` | Word documents with styles and heading levels |
| XLSX | `ExcelParser` | Each sheet → section, all tables preserved |
| CSV / TSV | `CSVParser` | Auto-detect delimiter (`,` `;` `\|` `\t`); encoding cascade; full table preserved |
| HTML | `HTMLParser` | h1–h6 hierarchy via BeautifulSoup |
| Markdown | `MarkdownParser` | ATX and Setext headings via mistletoe |

---

## 🔌 Provider Interfaces

All external dependencies sit behind swappable interfaces. Change the string — no other code changes.

### LLM Providers (`llm_provider=`)

| Value | Notes |
|---|---|
| `"groq"` | Fast, generous free tier — recommended for getting started |
| `"openai"` | GPT-4o-mini, GPT-4o |
| `"ollama"` | Fully local — `ollama pull llama3.2` |
| `"anthropic"` | Claude Haiku, Claude Sonnet |
| `"google"` | Gemini Flash, Gemini Pro |
| `"mistral"` | Mistral Large, Mixtral |
| `"together"` | Together AI hosted models |
| `"cohere"` | Command R+ |
| `"bedrock"` | AWS Bedrock (boto3 required) |

### Embedding Providers (`emb_provider=`)

| Value | Notes |
|---|---|
| `"huggingface"` | Local — downloads model once, then offline. **Default.** |
| `"openai"` | `text-embedding-3-small` / `text-embedding-3-large` |
| `"ollama"` | Local via Ollama (`nomic-embed-text`, etc.) |
| `"google"` | Vertex AI / Gemini embeddings |
| `"cohere"` | `embed-english-v3.0` |
| `"bedrock"` | AWS Bedrock Titan embeddings |
| `"nvidia"` | NVIDIA NIM embeddings |
| `"mistral"` | Mistral embeddings |

### Vector Backends (`vector=`)

| Value | Install | Best for |
|---|---|---|
| `"numpy"` (default) | built-in | Small docs, zero extra deps |
| `"faiss"` | `pip install faiss-cpu` | Fast ANN on large collections |
| `"chroma"` | `pip install chromadb` | Persistent cross-session store |

```python
from docnest.reader import UDFIndex

idx = UDFIndex.load("report.udf")                               # numpy (default)
idx = UDFIndex.load("report.udf", vector="faiss")              # FAISS
idx = UDFIndex.load("report.udf", vector="chroma",             # ChromaDB
                    persist_dir="./store")
```

### Search Providers

| Value | Notes |
|---|---|
| `"auto"` | Picks best available — bm25 → tfidf → keyword |
| `"bm25"` | BM25Okapi — best keyword recall |
| `"tfidf"` | TF-IDF — good fallback |
| `"keyword"` | Simple term overlap — zero deps |

---

## 🧪 Accuracy Benchmark — Multi-Format RAG Evaluation

**88 questions · 10 documents · 5 formats** — a comprehensive multi-format RAG evaluation.  
Numbers below are the latest **reproducible** run: answer model Cerebras `gpt-oss-120b`, scored
by the repo's judge (numeric + keyword, normalised). Reproduce with
`python eval/rag_accuracy_eval.py --model cerebras/gpt-oss-120b`.

### Accuracy by Format

| Format | Score | Pass Rate (≥ 7/10) | Questions |
|--------|-------|--------------------|-----------|
| 📊 XLSX | **9.6 / 10** | 93% | 15 |
| 📝 DOCX | **9.4 / 10** | ✅ 100% | 14 |
| 🌐 HTML | **9.3 / 10** | ✅ 100% | 14 |
| 📋 MD | **8.9 / 10** | 93% | 15 |
| 📄 PDF | **7.0 / 10** | 73% | 30 |

### Overall

| Metric | Value |
|--------|-------|
| **Average accuracy** | **8.5 / 10** |
| **Pass rate (≥ 7/10)** | **89% — 78 / 88 questions** |
| Documents | 10 across 5 formats |
| Answer model | Cerebras `gpt-oss-120b` |

> Structured/business formats (XLSX/DOCX/HTML/MD) score **8.9–9.6**; dense academic PDFs are
> the hardest at **7.0** and pull the average down. A prior run with the stronger
> `qwen-3-235b` model reached **9.55/10** (that model is no longer publicly accessible, so the
> reproducible `gpt-oss-120b` figure is reported here). Per-document detail and token/latency
> tables are in `eval/results/`.

---

### ⚡ DocNest vs Traditional RAG — Token Efficiency

Traditional RAG sends a fixed blind slice of every document for each question.  
DocNest retrieves **only the relevant sections** — anywhere in the document.

| Document | Format | Qs | Traditional RAG | DocNest | Saving |
|----------|--------|----|-----------------|---------|--------|
| TechVision Annual Report | DOCX | 14 | 35,224 | 11,789 | **−67%** |
| CloudMesh Architecture Spec | MD | 15 | 29,835 | 8,650 | **−71%** |
| NexusAPI Reference | HTML | 14 | 19,418 | 9,631 | **−50%** |
| Acme Corp Financials | XLSX | 15 | 48,840 | 38,991 | **−20%** |
| Constitutional AI Paper | PDF | 5 | 17,280 | 9,216 | **−47%** |
| IPCC AR6 | PDF | 5 | 17,280 | 22,946 | +33%¹ |
| GPT-3 Paper | PDF | 5 | 17,280 | 46,637 | +170%¹ |
| Llama 2 Paper | PDF | 5 | 17,280 | 46,888 | +171%¹ |
| **Total — 88 questions** | | **88** | **236,645** | **232,805** | **−2%** |

> ¹ Traditional baseline = first 3,456 tokens (blind top-slice — misses content buried in the document).  
> DocNest retrieves relevant chunks from *anywhere* in a 50-page paper. More tokens, but the **right** tokens.  
> On a real pipeline sending the **full** document: a 50-page PDF ≈ 80,000–120,000 tokens per question.  
> DocNest retrieves ~9,000 tokens — a **90 %+ reduction** while answering more accurately.

**Why this matters for cost:**

| Scenario | Model | Tokens / question | Cost / 1,000 Qs |
|---|---|---|---|
| Traditional (full-doc) | GPT-4o-mini | ~100,000 | ~$150 |
| Traditional (blind slice) | GPT-4o-mini | 3,456 | ~$5.20 — misses deep content |
| **DocNest** | GPT-4o-mini | ~2,600 avg structured · ~9,300 PDF | **~$4–14 — correct answers** |

---

### 4 Known Errors (out of 88)

| # | Document | Question | Root Cause |
|---|---|---|---|
| 1 | Acme XLSX | Highest monthly revenue | Retrieved December row instead of November |
| 2 | Acme XLSX | Total Enterprise tier ARR | Missing 4 accounts from retrieval (7,290 vs 7,600) |
| 3 | GPT-3 Paper | Architecture table (96L/96H/d=12288) | Dense figures-embedded table not indexed by PyMuPDF |
| 4 | Attention Paper | Dropout rate P_drop | Ablation row (0) ranked above method section (0.1) |

> All 4 errors are retrieval/indexing issues — **not LLM hallucination**.  
> DOCX, HTML, MD, and 3 out of 6 PDFs have **zero errors**.

---

### Run it yourself

```bash
# Fastest — Cerebras (free tier, no daily token limit)
pip install docnest-ai
export CEREBRAS_API_KEY="your-key"
python eval/rag_accuracy_eval.py --model cerebras/qwen-3-235b-a22b-instruct-2507 --run-id my_run

# Or with Groq (free tier)
export GROQ_API_KEY="gsk_..."
python eval/rag_accuracy_eval.py --model groq/llama-3.3-70b-versatile --run-id my_run

# Or with Gemini
export GOOGLE_API_KEY="your-key"
python eval/rag_accuracy_eval.py --model gemini-2.0-flash --run-id my_run
```

---

## 🗺 Roadmap

| Phase | Description | Status |
|---|---|---|
| **1** | Core parsers — PDF (Docling + PyMuPDF), DOCX, XLSX, HTML, MD | ✅ Done |
| **2** | Embedding + quantization (10+ providers via LangChain) | ✅ Done |
| **3** | Intelligence engine (summary, insights, key_numbers) | ✅ Done |
| **4** | UDF writer + reader + five-layer query engine | ✅ Done |
| **5** | Large PDF chunking — full ML quality, bounded RAM | ✅ Done |
| **6** | Library mode — multi-document cross-search | ✅ Done |
| **7** | PyPI release `pip install docnest-ai` | ✅ Done |
| **8** | PPTX parser — slides, speaker notes, embedded tables | 📋 Planned |
| **9** | EPUB parser — chapters, footnotes, embedded images | 📋 Planned |
| **10** | XML parser — configurable tag-to-section mapping | 📋 Planned |
| **11** | CSV / TSV parser — auto-header detection, delimiter sniffing, encoding cascade | ✅ Done |
| **12** | JSON / JSONL parser — nested object flattening, array tables | 📋 Planned |
| **13** | ODT / ODS parser — OpenDocument text and spreadsheet | 📋 Planned |
| **14** | RTF parser — rich text format documents | 📋 Planned |
| **15** | LaTeX / TeX parser — sections, equations, bibliography | 📋 Planned |
| **16** | Connectors: GitHub, Confluence, Notion, Jira | 📋 Planned |
| **17** | Hierarchical supervisor+worker for datasets > 200 MB | 📋 Planned |

Track detailed progress: [ROADMAP.md](ROADMAP.md)

---

## 📝 Blog

In-depth articles on how DOCNEST works and the problems it solves:

| # | Title | Published |
|---|-------|-----------|
| 1 | [My RAG app confidently told my client the wrong answer. I spent 3 days debugging the wrong thing.](https://dev.to/gunjantailor/i-built-a-pdf-parser-that-actually-preserves-table-structure-for-rag-heres-why-it-matters-19fo) | May 2026 |

---

## 🤝 Contributing

**DOCNEST is community-first.** We are building this in the open and want contributors at every level.

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
| [docnest](https://github.com/tailorgunjan93/docnest) | This library — document normalization engine |
| [udf-spec](https://github.com/tailorgunjan93/udf-spec) | Open specification for the `.udf` format |
| [knovex](https://github.com/tailorgunjan93/knovex) | Desktop RAG app powered by DOCNEST |
| [udf-reader-vscode](https://github.com/tailorgunjan93/udf-reader-vscode) | VS Code extension for `.udf` files |

---

<div align="center">

🔒 Secure · ⚡ Fast · 🛡️ Reliable · 💰 Cost-Effective

Built with ❤️ for the RAG community · [github.com/tailorgunjan93/docnest](https://github.com/tailorgunjan93/docnest)

</div>
