# Task — Large PDFs · QA / User Document

## What "working" means to a user
A user converts a 100+ page PDF (e.g. Llama 2 with a 101k-char appendix). It (a) doesn't blow
up memory, and (b) a question about a detail **buried deep** in a huge section is actually
found — not lost because the section got one truncated embedding.

## Test scenarios

### Passage chunking (`chunk_text`)
- Long text (> max_chars) → multiple passages, each ≤ max_chars; small overlap between them.
- Short text → exactly one passage (unchanged).
- Boundaries: splits on paragraph/sentence breaks; never splits mid-table block.
- Deterministic: same text → same passages.

### Retrieval improvement (Step 1 wired)
- A query matching content **late** in a giant section retrieves that section
  (regression of today's failure — currently the late content is unrepresented).
- Small/medium docs: retrieval results unchanged (single passage per section).

### Bounded embedding
- Embedding N sections records a **max batch ≤ batch_size** (monkeypatched embedder),
  proving peak memory is independent of N.

### Memory budget
- Converting the largest fixture PDF stays under a documented peak-RSS budget (tracemalloc/RSS
  assertion). Number set from a baseline measurement, with headroom.

### Regression / negative
- Net-new `chunking.py` imported by nothing until wired → no existing test changes (Step 1a).
- `.udf` format unchanged in Step 1 → all existing `.udf` files load identically.
- Empty / whitespace section → one (empty) passage, no crash.
- Full suite (`pytest -q`) green before and after each step.

## Definition of done (Step 1)
- `chunk_text` unit-tested; batched embedding tested; passage retrieval test shows deep-content
  recall improved; peak-RSS test passes; full suite green; owner gate before merge.
