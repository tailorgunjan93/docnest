# Task — Large PDFs (memory-bounded + retrievable) · BA / Functional Document

## WHY
Large PDFs are an active hardening target and the eval's weakest format. Measured root
cause (cached parsed docs) is **two-fold**, not just memory:

| Doc | Sections | Total chars | Biggest single section |
|-----|---------:|------------:|-----------------------:|
| Llama 2 | 21 | 264,183 | **101,295** |
| GPT-3 | 40 | 237,893 | **59,456** |
| BIS | 135 | 441,014 | 19,796 |

1. **Retrieval-quality bug (primary):** a 100k-char section receives **one** embedding, but
   the embedder truncates at ~512 tokens — so the vast majority of a giant section's content
   is **invisible to dense retrieval**. Deep facts (e.g. Llama 2 "Ghost Attention") can't be
   reliably found. This is *why* large PDFs answer poorly, independent of the LLM.
2. **Memory (NFR):** `UDFWriter.write()` embeds **all** sections in a single
   `embedder.embed([...all texts...])` call, and parsing accumulates every block/section in
   memory — both grow with document size, risking the bounded-memory NFR on 100s-of-pages PDFs.

## WHAT (required behaviour)
1. **Passage chunking:** sections beyond a size threshold are split into bounded passages,
   **each embedded separately**, so content deep in a large section is retrievable.
   Sectioning/headings and `.udf` readability are preserved (chunking is a retrieval-index
   concern, not a destruction of the section model).
2. **Bounded embedding:** embeddings are generated in **fixed-size batches**, so peak memory
   does not scale with section count / total text.
3. **Bounded, measurable memory:** converting a large PDF stays within a documented peak-RSS
   budget; a regression test asserts it.
4. **No quality regression** on small/medium docs; **improved recall** on large-PDF deep content.

### Acceptance criteria
1. A section > threshold (e.g. > ~2–4k chars) yields multiple passage embeddings; a query
   matching content *late* in a giant section retrieves it (it does not today).
2. Embedding a doc of N sections uses bounded peak memory (batched), verified by a test.
3. Peak RSS for converting the largest fixture PDF stays under a documented budget.
4. Full regression suite green; small-doc behaviour unchanged; `.udf`/`UDF_VERSION`/API intact.

### Non-goals
- Changing the human-facing section hierarchy (passages are an index-level addition).
- Streaming the entire pipeline to constant memory (bounded, not O(1)).
- A new embedding model (separate evaluation).

## HOW (functional flow)
parse (bounded) → normalise → **split oversized sections into passages** → **embed in
batches** → write `.udf` (passage vectors indexed; section text preserved). Retrieval matches
at passage granularity but still returns/ë attributes the parent section.

### Edge cases
- A single enormous section (101k chars) → many passages, bounded peak memory.
- Many small sections → batched embedding, no per-section overhead blow-up.
- Tables inside large sections → kept whole (not split mid-table).
- Empty / tiny sections → one passage (today's behaviour).
