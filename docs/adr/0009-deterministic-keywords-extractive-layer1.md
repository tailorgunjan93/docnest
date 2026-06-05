# ADR-0009 — Deterministic keywords + extractive Layer 1 (push 0-token to ≥70%)

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** Gunjan Tailor (owner)
- **Related:** ADR-0008 (key-numbers), retrospective §5.2/§5.3, docs/tasks/observers-tax/

## Context
After deterministic key-numbers, the Observer's-Tax zero-token rate reached 50% but stalled:
diagnosis showed the reader's **hybrid search returned empty** for most queries because
section `keywords` (the BM25 index source) were unpopulated → queries fell to the Layer-4
full-document fallback. And Layer 1 only fired when a precomputed `summary` existed (also
empty). So both 0-token layers were starved by missing deterministic intelligence.

## Decision
Two dependency-free, deterministic additions:
1. **`docnest/keywords.py`** (`extract_keywords`/`enrich_keywords`): salient per-section
   keywords (title terms + frequency over non-stopwords), wired into the pipeline so the
   reader's BM25 index ranks sections. No-op where already populated.
2. **Extractive Layer 1** in `reader.query`: when a section ranks confidently but has no
   precomputed summary, return the **question-relevant sentence(s)** extracted from that
   section (`_best_sentences`, keyword-overlap ranked) — a **0-token** answer grounded in the
   document. Empty string if no overlap (never fabricate).

## Consequences (measured, sample_report, 10 Q, local Ollama)
| Stage | Zero-token | Accuracy | Tax/query | vs naive |
|------|-----------:|---------:|----------:|---------:|
| empty intelligence | 0% | 90% | 331 | 31.8% |
| + key-numbers (ADR-0008) | 40% | 100% | 219 | 54.8% |
| + robust matching + duration fix | 50% | 100% | 184 | 62.1% |
| **+ keywords + extractive Layer 1** | **80%** | 90% | **38** | **92.1%** |

- **Zero-token 80% — exceeds the Charter's 70% goal.** L0+L1 (deterministic) answers are
  **100% accurate**; the 90% overall is the weak 1B model on the 2 remaining LLM-routed
  (Layer 3) questions — not the deterministic path.
- No `.udf`/`UDF_VERSION`/public-API change; all additive, no-op where populated.

## Alternatives considered
- **Vague precomputed summaries for Layer 1** — rejected: a generic section summary is not an
  answer to a specific question (would inflate zero-token rate at the cost of accuracy).
  Query-focused extraction returns the actual answer sentence.
- **LLM keyword/summary enrichment** — empty by default; costs tokens + network at ingest.
