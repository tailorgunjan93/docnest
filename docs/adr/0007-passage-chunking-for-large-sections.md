# ADR-0007 — Passage chunking for large sections (retrievability)

- **Status:** Accepted
- **Date:** 2026-06-04
- **Deciders:** Gunjan Tailor (owner)
- **Related:** docs/tasks/large-pdfs/, ADR-0006

## Context
Large PDFs produce pathologically large sections (Llama 2: one 101k-char section). The
writer embeds only `s.text[:300]` per section, and embedders truncate at ~512 tokens — so a
huge section's vector represents a tiny fraction of it, and **deep content is invisible to
dense retrieval**. This — not memory alone — is why large PDFs answer poorly.

## Decision
Add a pure, deterministic `docnest/chunking.py::chunk_text(text, max_chars, overlap)` that
splits a section's prose into bounded **passages** on paragraph/sentence boundaries, each
`<= max_chars`, with best-effort `overlap` for context continuity. Tiny text → a single
passage (today's behaviour). It is net-new and imported by nothing initially; wiring passages
into the retrieval build path (and later the `.udf`) are separate, gated steps.

## Consequences
- **Positive:** once wired, each passage is embedded separately → deep content in giant
  sections becomes retrievable; also enables bounded-memory batched embedding.
- **Neutral:** standalone module, zero blast radius until wired; no `.udf`/API change.
- **Cost:** more vectors per large doc (bounded by max_chars); chunking is O(n).

## Alternatives considered
- **Embed the whole section** — status quo; truncation loses deep content.
- **Raise the embed char cap only** — still bounded by the model's ~512-token truncation.
- **Fixed-size char windows ignoring structure** — rejected: splits mid-sentence/word;
  boundary-aware chunking preserves meaning. Tables are kept whole (chunking is prose-only).
