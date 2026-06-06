# DocNest — Testing Document (v0.7.0)

> **Authored from two lenses:** a **BA** defines *what must work and why it matters to a user*; a
> **Tester** defines *how we prove it* — explicit steps, expected results, and the regression view.
> Motto under test: **Secure · Fast · Reliable · Cost-Effective.**

This is the master test plan. Per-feature acceptance criteria live in each
`docs/tasks/<feature>/03-QA-user.md`; this document consolidates them, adds executable
step-by-step cases, and records what is covered vs. deferred.

---

## 1. Test strategy

| Level | Question it answers | Where |
|-------|--------------------|-------|
| **Unit** | Does each function do its one job (incl. edge/negative)? | `tests/test_*.py` |
| **Integration** | Do parser → normalizer → enrich → write → read compose correctly? | `tests/test_pipeline.py`, `tests/test_writer.py`, `tests/test_reader.py` |
| **Functional** | Does a real `.udf` answer real questions at the right layer/cost? | `tests/test_reader.py`, `eval/observers_tax_eval.py` |
| **End-to-end (accuracy)** | On real docs, how correct are the answers, and at what token cost? | `eval/rag_accuracy_eval.py`, `eval/observers_tax_phase2.py` |
| **Regression** | Did anything that worked before break? | full suite, every cycle — *grows only* |

**Test-first rule (Development Protocol):** every change adds a test that **fails first**, then
passes. Defects found in dev get a regression test **before** the fix; escaped defects also get a
root-cause note on why they weren't caught.

**Current footprint:** **780 automated tests** across **31 files** — **775 passing, 5 skipped**
(environment-gated OCR / Docling integration tests). Target: full suite green every cycle; only
all-green earns the ✅ mark. *Per-file counts below are `def test_` definitions; pytest's collected
total is higher because of parametrized cases.*

---

## 2. Scenario coverage map (by area)

| Area | Tests | What it proves | Source of truth |
|------|------:|----------------|-----------------|
| Parsers (PDF/DOCX/XLSX/HTML/MD/CSV) | 74 + 60 + 39 + 24 | Structure, headings, tables extracted per format | `test_parsers.py`, `test_csv_parser.py`, `test_docx_parser.py`, `test_md_parser.py` |
| Five-layer reader | 53 | Right layer chosen, right answer, right token cost | `test_reader.py` |
| HTML viewer | 51 | Self-contained HTML, TOC, table render | `test_viewer.py` |
| CLI | 43 | `convert/query/inspect/view/library` commands | `test_cli.py` |
| Writer / `.udf` archive | 36 | ZIP layout, batched embedding, format version | `test_writer.py` |
| Quantizer | 34 | float32/16/int8/binary round-trips | `test_quantizer.py` |
| Intelligence engine | 34 | LLM enrichment (summaries/insights) | `test_intelligence.py` |
| Normalizer | 31 | `§id` assignment, hierarchy | `test_normalizer.py` |
| Vector / search backends | 29 + 25 | numpy/faiss/chroma · bm25/tfidf/keyword | `test_vector_backends.py`, `test_search_providers.py` |
| Library mode | 26 | multi-doc index, cross-doc search | `test_library.py` |
| Connectors | 25 | connector base + adapters | `test_connectors.py` |
| Models | 23 | Pydantic schemas / validation | `test_models.py` |
| Storage backends | 20 | zip / dir | `test_storage_backends.py` |
| Pipeline (integration) | 20 | end-to-end convert path | `test_pipeline.py` |
| OCR providers | 18 + 8 | scanned-PDF text (Hindi+English) | `test_ocr_providers.py`, `test_pymupdf_ocr.py` |
| **Table aggregation** ⭐ | 17 | deterministic sum/count/min/max/avg, fail-closed | `test_aggregation.py` |
| Source compaction | 14 | path compaction | `test_source_compaction.py` |
| **Key numbers** ⭐ | 11 | regex metric extraction + label binding | `test_key_numbers.py` |
| **Keywords** ⭐ | 9 | frequency/title keyword index | `test_keywords.py` |
| **Chunking** ⭐ | 7 | large-PDF passage splitting | `test_chunking.py` |
| Table rendering | 6 | budgeted table → context | `test_table_rendering.py` |
| **PyMuPDF tables** ⭐ | 5 | `find_tables` native extraction | `test_pymupdf_tables.py` |
| **HTML tables** ⭐ | 4 | rowspan/colspan grid | `test_html_tables.py` |
| **DOCX tables** ⭐ | 4 | merged-cell grid | `test_docx_tables.py` |
| **Embed batching** ⭐ | 4 | bounded-memory batch embed | `test_embed_batching.py` |
| Embedder | 2 | model wrapper | `test_embedder.py` |

⭐ = new or hardened in **v0.7.0**.

---

## 3. Functional test cases — v0.7.0 features

Each case is **Given / When / Then** so a tester can run it by hand or trace it to an automated
test. IDs are stable references for defect reports.

### 3.1 Deterministic intelligence (0-token answer path) — ADR-0008

> **BA:** A user asking a factual question ("What's the SLA uptime?", "How much was Q3 revenue?")
> should get the **correct** answer **without paying any LLM tokens**. The library's own logic is
> the brain; the LLM is only a narrator when synthesis is genuinely needed.

| ID | Scenario | Steps | Expected |
|----|----------|-------|----------|
| DET-1 | Key-number recall | Convert a doc with "Uptime: 99.95%" → `query("what is the uptime")` | Answer `99.95%`, `layer_used=0`, `tokens_used=0` |
| DET-2 | Label binding | Doc has `ISO 27001`, `AZ-204`, `142ms` | Each extracted with correct label; identifiers not split into bare numbers |
| DET-3 | Bare-year / list-marker filter | Doc has "in 2024" and "1. Item" | Neither captured as a key number |
| DET-4 | Keyword index non-empty | Convert any doc → inspect keywords | Title terms + top frequency terms present (BM25 index not empty) |
| DET-5 | Extractive Layer 1 | Ask a factual Q with no precomputed summary | Returns query-focused sentence at `tokens_used=0` (not a Layer-4 escalation) |
| DET-6 | Ambiguity guard | Query matches two key numbers equally | Does **not** return a confidently-wrong single value |

**Acceptance (measured):** factual zero-token answer rate **0% → 80%**, **100% accurate** when it
fires, **~92% fewer tokens** on the sample report. (See `eval/observers_tax_eval.py`.)

### 3.2 Complex tables — ADR-0006

> **BA:** A value buried in row 11, or a "which row is highest / what's the total" question, must be
> answered from **all** rows — not just the first few — and column meaning must survive merged cells.

| ID | Scenario | Steps | Expected |
|----|----------|-------|----------|
| TBL-1 | Row truncation | 12-row table → "highest value" and "sum" | Correct, computed over **all 12 rows** |
| TBL-2 | Over-budget table | Very large table → query | Bounded context + "+N more rows" note |
| TBL-3 | HTML spans | Table with `rowspan`/`colspan` | Rows align to headers; spanned value repeated; no column shift |
| TBL-4 | DOCX merged cells | Merged header/data | Grid aligned, value preserved |
| TBL-5 | XLSX merged ranges | Merged ranges + multi-table sheet | Ranges filled; sheet split correctly |
| TBL-6 | Multi-row header | 2-row header | Single combined-label row (`"Q3 — Revenue"`) |
| TBL-7 | PyMuPDF native | Text PDF with bordered table | ≥1 `TableData(headers, rows)` via `find_tables` |

### 3.3 Deterministic table aggregation — ADR-0004

> **BA:** "Sum this column", "which row has the max", "count rows where X" should be answered by
> **code**, deterministically, never by asking the model to do arithmetic.

| ID | Scenario | Steps | Expected |
|----|----------|-------|----------|
| AGG-1 | Sum / avg / min / max / count | `TableQuery.aggregate(...)` over a column | Exact numeric result |
| AGG-2 | Fuzzy column resolve | Query "revenue" vs header "Revenue (USD)" | Resolves to correct column |
| AGG-3 | Row filter | `eq` / `contains` / `gt` / `lt` predicates | Correct row subset |
| AGG-4 | Fail-closed | Ambiguous/missing column or non-numeric cells | Returns `AggregationResult` failure, **no guess** |
| AGG-5 | Number parsing | `$12,550`, `1 200,50`, `210 000` | Parsed to correct float |

### 3.4 Large & scanned PDFs — ADR-0007 / OCR

> **BA:** A 200-page PDF must convert within bounded memory; a scanned/image PDF must still yield
> searchable text (Hindi + English).

| ID | Scenario | Steps | Expected |
|----|----------|-------|----------|
| PDF-1 | Passage chunking | Long section → `chunk_text(max=2000, overlap=200)` | Boundary-aware passages, overlap preserved |
| PDF-2 | Bounded-batch embed | Convert large doc | `embed_in_batches(batch=64)`; memory does not grow unbounded |
| PDF-3 | Scanned PDF OCR | Image-only PDF → convert | Text extracted; sections created |
| PDF-4 | Bilingual OCR | Hindi + English page | Both scripts recovered |

### 3.5 Observer's Tax (cost measurement) — ADR / eval

> **BA:** We must be able to **prove** the cost claim — how many tokens the model is forced to read
> per query, and how much the deterministic path saves.

| ID | Scenario | Steps | Expected |
|----|----------|-------|----------|
| OTX-1 | Per-query token accounting | Run `observers_tax_eval.py` on a `.udf` | Reports tokens per query, per layer |
| OTX-2 | With-LLM vs deterministic-only | Run `observers_tax_phase2.py` | Side-by-side correctness vs token cost |
| OTX-3 | Tuned local judge | Judge scores known-correct answers | `12 550`, `210 000`, `§N`/`Section N` credited correctly |

---

## 4. End-to-end accuracy (RAG eval)

> **BA:** "Working" ultimately means *correct answers on real documents*. We report **reproducible**
> numbers only, and name the model.

**Harness:** `eval/rag_accuracy_eval.py` — 88 questions, 10 documents, 5 formats. Token cap 1024.
Judge: `_local_judge` (number/locator-normalizing, result-over-formula credit).

| Run | Model | Score | Pass rate | Notes |
|-----|-------|------:|----------:|-------|
| **v0.7.0 reference** | Cerebras `gpt-oss-120b` | **8.5/10** | **89%** | Reproducible; per-format below |
| Phase 2 (PDF focus) | Cerebras `gpt-oss-120b` | 8.3/10 | 83% | 0 empty answers |
| Historical peak | `qwen-3-235b` | 9.55/10 | 95.5% | Model no longer publicly accessible — **not** a current claim |

**Per-format (gpt-oss-120b):** XLSX 9.6 · DOCX 9.4 · HTML 9.3 · MD 8.9 · **PDF 7.0** (weakest;
active hardening target).

**Acceptance gate:** a change must **not regress** the reference run. PDF synthesis is the known
frontier; improvements there are tracked, not blockers for unrelated changes.

---

## 5. Regression view (must never break)

- [ ] Full suite green (**775 passing / 5 env-skipped**).
- [ ] `.udf` format + existing files load unchanged (`UDF_VERSION` backward-compatible).
- [ ] Public API + CLI flags unchanged (PyPI `docnest-ai` consumers).
- [ ] Simple single-header / single-table cases still pass (not just the new merged-cell paths).
- [ ] Accuracy eval ≥ v0.7.0 reference (8.5/10, 89%) on the 88-Q suite.
- [ ] No new unbounded-memory or non-lazy-import paths (NFR budgets).

---

## 6. Negative & edge cases (explicitly covered)

| Case | Expected behaviour |
|------|--------------------|
| Empty / whitespace-only document | Convert succeeds; no sections; no crash |
| Table with non-numeric cells in a summed column | Aggregation **fails closed**, no guess |
| Query matching nothing | Graceful "no answer" / escalation, never a fabricated value |
| `allow_llm=False` | Reader returns `layer_used=-1, tokens_used=0` (deterministic-only mode) |
| Corrupt / truncated `.udf` | Clear error, no partial-state crash |
| Bare years, list markers, identifiers | Excluded from key numbers (DET-2, DET-3) |
| Over-token-budget context | Truncated with "+N more rows / sections" note |

---

## 7. How to run

```bash
# Full suite (regression-first, every cycle)
pytest -q

# One area
pytest tests/test_aggregation.py -q
pytest tests/test_key_numbers.py tests/test_keywords.py -q

# Coverage
pytest --cov=docnest --cov-report=term-missing

# Accuracy eval (needs an LLM provider; cap 1024)
#   Windows console: set PYTHONUTF8=1 to avoid cp1252 emoji crashes
python eval/rag_accuracy_eval.py

# Cost / Observer's Tax
python eval/observers_tax_eval.py          # layered .udf reader
python eval/observers_tax_phase2.py        # with-LLM vs deterministic-only
```

> **Windows note:** Store Python lives at
> `%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe`; set `PYTHONUTF8=1` and
> `PYTHONIOENCODING=utf-8` before eval runs to avoid console encoding crashes.

---

## 8. Deferred / not yet covered (honest gaps)

| Item | Status | Why |
|------|--------|-----|
| Aggregation engine wired into the **reader** | Built + 17 tests; **not yet wired** | Pending the dual-retriever consolidation |
| Multi-aspect **query decomposition** | On parked branch `task/query-decomposition` | Validation +2/-1, unproven — not merged |
| Synthesis-aware LLM routing | Reverted | +1 accuracy for 4× tokens — net-negative |
| PDF synthesis accuracy (7.0) | Active hardening target | Dense-prose synthesis is the frontier |
| JSON / PPTX / EPUB parsers | Roadmap | Not started |

---

*Traceability: feature acceptance criteria → `docs/tasks/<feature>/03-QA-user.md`; the permanent
"why" → `docs/adr/`; release history → `CHANGELOG.md`.*
