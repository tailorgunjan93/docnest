# ADR-0008 — Deterministic key-number enrichment (revive the 0-token path)

- **Status:** Accepted
- **Date:** 2026-06-05
- **Deciders:** Gunjan Tailor (owner)
- **Related:** retrospective §5.1, ADR-0004 (aggregation), docs/tasks/observers-tax/FINDINGS.md

## Context
The Observer's-Tax eval showed the 0-token answer rate is **0%** (Charter goal: 70%) because
`key_numbers` — which power Layer 0 — are **LLM-generated at ingest and empty by default**.
Extracting figures from text is deterministic (regex + label binding), so DocNest can do it
itself, for free, every time.

## Decision
Add `docnest/key_numbers.py` (`extract_key_numbers`, `enrich_key_numbers`, `parse_number`):
deterministic, dependency-free extraction of labelled figures (currency, %, durations,
ratios, counts) with noise filtering (bare years, list-marker ordinals, identifiers like
`ISO 27001`/`AZ-204`) and nearest-`Label:` binding. Wire `enrich_key_numbers` into the
pipeline (Stage 5b) so `key_numbers` are populated **by default, with no LLM** — a no-op if
an LLM (or caller) already populated them.

## Consequences (measured on sample_report)
- **Zero-token rate 0% → 40%**, **accuracy 90% → 100%** (Layer-0 answers are exact),
  **Observer's Tax 331 → 219 tokens/query** (31.8% → 54.8% reduction vs naive RAG).
- No `.udf`/`UDF_VERSION`/public-API change; existing files unaffected; LLM enrichment still
  wins when configured.
- Remaining gap to 70%: prose figures get verbose labels that don't match question wording
  (e.g. "Monthly cloud spend dropped"); follow-ups are better label binding, deterministic
  section summaries (Layer 1), and wiring the aggregation engine for "total/sum" queries.

## Alternatives considered
- **Keep LLM-only enrichment** — rejected: empty by default → 0-token path dead; costs tokens
  + a network call at ingest; non-deterministic.
- **Add YAKE/quantulum3 deps** — deferred: regex + label binding already covers figures with
  zero new dependency (NFR: deps lazy/pinned/minimal).
