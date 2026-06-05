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

The 0-token path is revived and Layer-0 answers are *exact*. Remaining gap to 70%: prose
figures get verbose labels that don't match question wording, and there's no Layer-1 summary
yet. Next: better label binding, deterministic section summaries (Layer 1), and wiring the
aggregation engine (ADR-0004) for "total/sum" queries.

## Re-run
```
python eval/observers_tax_eval.py --udf <file.udf> --provider ollama --model llama3.2:1b
```
