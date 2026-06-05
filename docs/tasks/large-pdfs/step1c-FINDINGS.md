# Large PDFs · Step 1c — passage→retrieval wiring · INVESTIGATED, NOT SHIPPED

**Decision (2026-06-05):** prototyped passage-level dense retrieval (chunk sections →
embed passages → HNSW over passages → dedup hits back to sections), then **discarded it**
— the end-to-end benefit over the existing retrieval is unproven and it's a Medium-risk
change to the core path. Same evidence-driven discipline applied to query-decomposition.

## What was measured
- **Dense-only, real Llama 2 doc:** an *exact* deep sentence ranked the 101k-char section
  **#15/21 section-level vs #1/21 passage-level** — a real dense-path gain.
- **But end-to-end it doesn't clearly help**, because:
  1. The full retriever fuses **FTS5**, which indexes the *entire* section text — so deep
     **keyword** matches are already found regardless of position. The retrieval-correctness
     audit never showed a deep-content *failure* attributable to truncated section vectors.
  2. For **semantic/paraphrase** deep queries (where FTS can't help), a controlled test
     showed passage-dense **still buries** the deep section: the deep marker passage is
     *diluted* (chunked together with neighbouring prose), and purer competing sections
     out-rank it. Passage-dense rank of the deep section: still last (#8/8) in that setup.

## Conclusion
The hypothesis ("giant sections hide deep content from retrieval") is real for the dense
sub-signal, but the existing **FTS + section-dense + graph** fusion already covers the cases
that matter, and passage-dense adds dilution risk without a demonstrable end-to-end win.
Shipping it would add Medium-risk complexity to core retrieval for unproven benefit.

## What WAS shipped from #4 (the proven parts)
- `docnest/chunking.py::chunk_text` — deterministic passage splitting (ADR-0007) — a reusable
  building block (e.g. for the future `.udf` passage-persistence step, or query-side packing).
- `embedder.embed_in_batches` + `UDFWriter(embed_batch_size=…)` — **bounded-memory** embedding
  (the genuine large-PDF NFR win), merged + on PyPI-track.

## Re-open criteria
Revisit passage-level retrieval if (a) a stronger embedder is adopted (semantic deep recall
becomes reliable), or (b) an eval case shows deep content that FTS misses and section-dense
buries. Then chunk on **semantic boundaries** (avoid diluting the answer passage) and measure
end-to-end recall, not just the dense sub-signal.
