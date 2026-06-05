# Observer's Tax eval (#5) — findings

**Observer's Tax** = the tokens the LLM must "pay" to *observe* (read) context per query.
DocNest's premise: Layer 0 (precomputed intelligence) and Layer 1 (BM25+cosine) answer for
**0 tokens**; only Layers 2–4 pay. The accuracy eval measured the HybridRetriever path (which
always calls the LLM); this harness measures the **production `.udf` reader** (`UDFIndex.query`,
the layered path) — so it's the first honest look at the tax.

Harness: `eval/observers_tax_eval.py` (local, no quota; Ollama llama3.2:1b for Layers 2–4).

## Result — `sample_report.udf` (10 questions)
| Metric | Value |
|---|---|
| Zero-token answers (L0+1) | **0 / 10 (0%)** — Charter goal is 70% |
| Accuracy | 90% |
| Layer distribution | Layer 2: 1q · **Layer 4: 9q** (no L0/L1) |
| DocNest tax | 331 tokens/query |
| Naive-RAG tax | 486 tokens/query |
| Tax reduction | **31.8%** |

## What this proves (honest)
1. **The 0-token path is dead in practice.** Layer 0 needs `key_numbers`/`insights` and Layer 1
   needs section `summary` — all **LLM-generated at ingest and empty by default** (the writer
   never populated them here). So the Charter's "70% of queries at 0 tokens" is currently **0%**.
   This is the same root cause as the retrospective: the intelligence layer is outsourced to an
   LLM at ingest and usually unpopulated.
2. **Escalation collapses to Layer 4.** 9/10 queries fell all the way to the full-document
   fallback — Layer 1 was skipped (no summaries) and Layer 2's section ranking wasn't confident
   enough, so the layered design degenerated into "read the whole doc." On a small doc that's
   cheap (≈ naive RAG); on a large doc it would be the worst case.
3. **The tax reduction (31.8%) is real but far below potential.** It comes only from Layer 4
   trimming, not from the intended free Layers 0/1.

## Implication (validates the roadmap)
The single highest-leverage fix is to **populate the intelligence layer deterministically**
(retrospective §5.1 key-number extraction — already prototyped, 37 numbers extracted with no
LLM; §5.2 keywords; §5.3 summaries). That would:
- turn lookup/aggregation queries into **Layer 0 (0-token)** hits → move the zero-token rate
  off 0% toward the Charter's 70%;
- give Layer 1 the `summary` it needs to fire.
Then re-run this harness to measure the tax drop. The aggregation engine (ADR-0004) is the
deterministic Layer-0 answerer for "total/sum/count" queries once wired into the reader.

## Follow-up result — deterministic key-number enrichment (ADR-0008)
After wiring deterministic `key_numbers` extraction into the pipeline (no LLM) and
re-running the same 10 questions on the enriched `.udf`:

| Metric | Before (empty) | After (deterministic) |
|---|---|---|
| Zero-token answers (L0+1) | 0/10 (0%) | **4/10 (40%)** |
| Accuracy | 90% | **100%** |
| Layer distribution | L2:1, L4:9 | **L0:4**, L4:6 |
| DocNest tax | 331 tok/q | **219 tok/q** |
| Tax reduction vs naive | 31.8% | **54.8%** |

The 0-token path is revived and Layer-0 answers are *exact*.

## Reaching (and exceeding) the 70% goal
Full progression on the same 10 questions (local Ollama):

| Stage | Zero-token | Accuracy | Tax/query | vs naive |
|------|-----------:|---------:|----------:|---------:|
| empty intelligence | 0% | 90% | 331 | 31.8% |
| + deterministic key-numbers (ADR-0008) | 40% | 100% | 219 | 54.8% |
| + robust Layer-0 matching + duration-extraction fix | 50% | 100% | 184 | 62.1% |
| **+ deterministic keywords + extractive Layer 1 (ADR-0009)** | **80%** | 90% | **38** | **92.1%** |

**80% zero-token — exceeds the Charter's 70% goal.** The jump from 50%→80% came from two
diagnosed root causes: (1) the reader's hybrid search returned *empty* because section
`keywords` were unpopulated → fixed with deterministic keyword extraction; (2) Layer 1 only
fired on a precomputed summary → added query-focused **extractive Layer 1** (the answer
sentence at 0 tokens). L0+L1 answers are **100% accurate**; the 90% overall is the weak 1B
model on the 2 remaining LLM-routed (Layer 3) questions, not the deterministic path.

## Phase 2 (PDFs) — with-LLM vs deterministic-only (no LLM)
`eval/observers_tax_phase2.py` builds a `.udf` per PDF (cached parse + deterministic
key_numbers + keywords) and runs each question both ways (reader `allow_llm` flag). 30 PDF
questions, local Ollama:

| Mode | Answered | Correct | Tokens/query |
|---|---|---|---|
| Deterministic-only (no LLM) | 25/30 (83%) | 12/30 (40%) | **0** |
| With-LLM (full stack) | — | 15/30 (50%) | 35 |

- **Deterministic-only answers 83% of PDF questions at 0 tokens and captures ~80% of the
  LLM's accuracy (40% vs 50%).**
- **The LLM adds only +10% accuracy for ~35 tok/query** — cheap because 22/30 questions
  resolve at Layer 1 (0 tokens) even in LLM mode; only ~5 escalate (layer dist {0:3,1:22,2:2,3:3}).
- **Boundary:** deterministic extraction excels at structured/factual queries (sample_report:
  80% zero-token, 100% accurate on L0/L1) but is weaker on academic-PDF *synthesis* questions
  (40%), which genuinely need reasoning — supplied cheaply by the LLM over L1-narrowed context.

## Re-run
```
python eval/observers_tax_eval.py    --udf <file.udf> --provider ollama --model llama3.2:1b
python eval/observers_tax_phase2.py  # PDFs, with-LLM vs deterministic-only
```
