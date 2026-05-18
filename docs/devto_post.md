# TITLE
I built a PDF parser that actually preserves table structure for RAG — here's why it matters

# TAGS
rag, python, ai, llm

# COVER IMAGE
(use the before/after screenshot or the logo from docs/logo.svg)

---

# BODY

Every RAG tutorial shows the same pipeline:

```
PDF → extract text → split every 512 tokens → embed → store → query
```

It works fine for blog posts. It completely falls apart for anything structured.

## The problem nobody talks about

Take a financial report. It has a revenue table:

| Region   | Q2 Revenue | Q3 Revenue | Change  |
|----------|-----------|-----------|---------|
| Europe   | 38.1%     | 45.2%     | +7.1pp  |
| Asia     | 29.3%     | 41.7%     | +12.4pp |
| Americas | n/a       | 52.1%     | —       |

After blind chunking, your LLM receives:

```
"45.2%  Q3  Europe  38.1%  Q2  Europe  41.7%  Q3  Asia   29.3%"
```

Numbers with no column headers, no caption, no context. Ask it "which region grew the most?" and you get an approximate guess — not an answer.

The same problem happens with:
- Legal contracts (clause split mid-sentence)
- API docs (code example separated from its description)  
- Research papers (figure caption disconnected from its analysis)

This isn't a retrieval problem. It's an ingestion problem.

## What I built

I spent the last few months building **DOCNEST** — a document normalization engine that reads structure before touching content.

Instead of chunks, every heading becomes a navigable `§section`. Every table is preserved as structured JSON. Every section gets a one-sentence summary and a keyword index — computed once at ingest.

The output is a `.udf` file (Unified Document Format) — a self-contained portable knowledge base.

```python
from docnest.parsers.pymupdf_pdf import PyMuPDFParser
from docnest.normalizer import SectionNormaliser
from docnest.writer import UDFWriter
from docnest.reader import UDFIndex

# Parse → normalise → save (no API key needed)
raw = PyMuPDFParser().parse("report.pdf")
doc = SectionNormaliser().normalise(raw)
UDFWriter().write(doc, "report.udf")

# Query
idx = UDFIndex.load("report.udf")
result = idx.query(
    "Which region had the highest Q3 growth?",
    llm_provider="groq",
    llm_model="llama-3.3-70b-versatile",
    llm_api_key="gsk_...",  # free at console.groq.com
)
print(result.answer)      # "Asia grew the most at +12.4pp"
print(result.layer_used)  # 1 — answered from index, 0 LLM tokens used
```

## The five-layer query engine

The part I'm most proud of is how queries are resolved:

| Layer | Mechanism | Tokens | When it fires |
|-------|-----------|--------|---------------|
| 0 | Pre-computed (summary, key numbers) | **0** | Direct match |
| 1 | BM25 + cosine → navigate to §section | **0** | Strong keyword match |
| 2 | Section-scoped LLM | ~300 | Needs interpretation |
| 3 | Multi-section synthesis | ~900 | Cross-section reasoning |
| 4 | Full document fallback | ~4000 | Nothing else worked |

**Layers 0 and 1 answer roughly 70% of real-world questions with zero LLM tokens.** You pay for compute only when the question genuinely requires it.

## How it handles large PDFs

Docling (the ML-quality PDF parser) loads full models into RAM. A 600-page PDF would exhaust memory on most machines.

DOCNEST solves this with automatic page chunking:

```python
from docnest.parsers.pdf import DoclingPDFParser

# Auto-chunks PDFs > 30 pages — peak RAM = one chunk, not the whole file
raw = DoclingPDFParser().parse("600-page-annual-report.pdf")

# Or tune explicitly
raw = DoclingPDFParser(chunk_pages=10).parse("report.pdf")  # low RAM
raw = DoclingPDFParser(chunk_pages=50).parse("report.pdf")  # high RAM
```

PyMuPDF splits the PDF into N-page temp files. Docling processes each chunk at full ML quality. Sections are merged. The output is identical to processing the whole file at once.

## Accuracy on a real document

I ran 25 questions against a 500-page open-source nutrition textbook using PyMuPDF + Groq's free tier:

- Basic facts (calories, macronutrients): **5/5**
- Macronutrient detail (fiber, glycemic index): **5/5**
- Micronutrients (vitamins, minerals): **4/5**
- Hard synthesis (BMR, omega-3, antioxidants): **5/5**
- Edge cases (hallucination, tables, out-of-scope): **5/5**

**24/25 (96%)** — the one failure was a table-only page where the text parser extracted no content (switch to DoclingPDFParser for those).

## Try it

```bash
pip install docnest-ai pymupdf
```

GitHub: https://github.com/tailorgunjan93/docnest  
PyPI: https://pypi.org/project/docnest-ai

It supports PDF (Docling + PyMuPDF), DOCX, XLSX, HTML, and Markdown. LLM providers: Groq, OpenAI, Ollama, Anthropic, Google, Mistral and more. Vector backends: numpy (default), FAISS, ChromaDB.

I'm building this in the open. If you've hit this table-structure problem in your own RAG pipeline, I'd genuinely like to hear what broke.
