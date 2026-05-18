# ══════════════════════════════════════════════════════
# POST 1 — r/LocalLLaMA
# ══════════════════════════════════════════════════════

SUBREDDIT: r/LocalLLaMA
FLAIR: Project

TITLE:
Built a PDF parser that preserves table structure for local RAG — tired of blind chunking destroying context

BODY:
Anyone else frustrated that PDF → LangChain loader → chunk → embed turns
perfectly good tables into meaningless number soup?

I've been building **DOCNEST** to fix this. Instead of blind chunking, it reads
document structure first:

- Every heading → navigable §section with BM25 keywords + embedding
- Every table → `{ caption, headers, rows[] }` JSON (not flattened text)
- Five-layer query engine: BM25+cosine at layer 1 answers ~70% of questions
  with zero LLM tokens

Works fully local with Ollama:

```python
from docnest.pipeline import DocNestPipeline

pipeline = DocNestPipeline(
    llm_provider="ollama",
    llm_model="llama3.2",
    emb_provider="huggingface",
    emb_model="all-MiniLM-L6-v2",
)
pipeline.convert("report.pdf")   # → report.udf
```

Also handles large PDFs (600+ pages) without OOM by auto-chunking through
PyMuPDF and running Docling at full ML quality on each chunk.

`pip install docnest-ai pymupdf`

GitHub: https://github.com/tailorgunjan93/docnest

Curious if others have hit this table-destruction problem in local RAG setups.


# ══════════════════════════════════════════════════════
# POST 2 — r/LanguageModelTooling  (or r/LangChain)
# ══════════════════════════════════════════════════════

SUBREDDIT: r/LanguageModelTooling
FLAIR: Tool / Library

TITLE:
DOCNEST — document normalization engine: parse PDF/DOCX/XLSX into structured §sections instead of blind chunks

BODY:
I built DOCNEST to address a specific problem I kept running into: standard
PDF loaders destroy table structure, split clauses mid-sentence, and disconnect
figure captions from their analysis.

**What it does differently:**
- Reads document structure (headings, tables, lists) before extracting text
- Every table preserved as `{ caption, headers, rows[] }` — not flattened
- Keyword index (BM25) + quantized embeddings built at ingest time
- Five-layer query resolution — tries cheapest layer first, escalates only if needed
- Output is a portable `.udf` file you can share like any other file

**Supports:**
- Parsers: PDF (Docling ML + PyMuPDF fast), DOCX, XLSX, HTML, Markdown
- LLMs: Groq, OpenAI, Ollama, Anthropic, Google, Mistral, Together, Cohere
- Vectors: numpy (built-in), FAISS, ChromaDB

```bash
pip install docnest-ai pymupdf
```

Benchmark: 24/25 (96%) on a 500-page nutrition textbook, out of the box.

GitHub: https://github.com/tailorgunjan93/docnest
PyPI: https://pypi.org/project/docnest-ai


# ══════════════════════════════════════════════════════
# POST 3 — r/MachineLearning (gentler, more technical)
# ══════════════════════════════════════════════════════

SUBREDDIT: r/MachineLearning
FLAIR: Project

TITLE:
[Project] Document normalization engine for RAG — preserves table structure, five-layer query resolution, 96% accuracy on 500-page benchmark

BODY:
I've been working on a document ingestion layer for RAG that addresses the
structural information loss that happens during standard PDF → chunk → embed
pipelines.

**Core idea:** instead of character-based chunking, parse the document's
structure first. Each heading becomes a navigable section node with:
- Title, level, parent section reference
- BM25 keyword index built from section text
- Quantized float16 embedding
- One-sentence LLM summary (optional, computed once at ingest)

Tables are extracted as `{ caption, headers, rows[] }` objects rather than
flattened text strings, which means the LLM receives column-header context
alongside each cell value.

**Query resolution is layered:**
0. Pre-computed (summary, key numbers) — 0 tokens
1. BM25 + cosine → navigate to §section — 0 tokens  
2. Section-scoped LLM — ~300 tokens
3. Multi-section synthesis — ~900 tokens
4. Full document fallback — ~4000 tokens

Layers 0-1 handle ~70% of real-world factual queries with zero inference cost.

**Large PDF handling:** Auto-chunks PDFs > 30 pages through PyMuPDF, runs
Docling at full ML quality on each chunk, merges sections. Peak RAM stays
bounded regardless of document size.

**Benchmark:** 25 questions across 5 difficulty tiers against a 500-page
open-source textbook — 24/25 (96%) correct, no fine-tuning.

`pip install docnest-ai` | https://github.com/tailorgunjan93/docnest

Happy to discuss the architecture or the UDF format spec.
