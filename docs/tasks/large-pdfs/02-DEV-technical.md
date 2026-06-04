# Task — Large PDFs · DEV / Technical Document

## Confirmed root causes (from code + cached docs)
- **`UDFWriter.write()`** embeds `(s.summary or s.title + " " + s.text[:300])` per section
  (writer.py:120-124) — i.e. **≤300 chars** represent a whole section. A 101k-char section
  is ~99.7% unrepresented in its vector. (The `HybridRetriever` build path embeds fuller
  text but the model still truncates at ~512 tokens.)
- **Single-batch embed:** `self.embedder.embed(texts)` is called once over **all** sections.
- **Parse accumulation:** `_extract_blocks` builds a flat list of every span across all pages.

## Design — phased, lowest-risk first

### Step 1 — passage chunking + batched embedding (no `.udf` format change)
- **New `docnest/chunking.py`** (pure, deterministic, dependency-free):
  `chunk_text(text, max_chars=2000, overlap=200) -> list[str]` — split on paragraph/sentence
  boundaries, never mid-table; bounded passage size; small overlap for context continuity.
  Tiny text → single passage (today's behaviour).
- **Batched embedding:** add `batch_size` to the embedder wrappers / a writer-level loop so
  `embed` processes texts in fixed-size chunks (e.g. 64) — peak memory independent of N.
- **Wire into the `HybridRetriever` build path** (retrieval.py): index **passages** (each with
  a parent-section id), so deep content is retrievable; results map back to the parent section.
  This improves the eval/retrieval path **without** touching the `.udf` format.

### Step 2 — persist passage embeddings in `.udf` (separate gate)
- Add an **optional, backward-compatible** `passages` array per section in the embedding blob /
  catalogue (old readers ignore it; old `.udf` files still load). Reader path then matches at
  passage granularity. Decide UDF_VERSION policy here (likely a backward-compatible minor note,
  not a breaking bump). **Own impact/risk pass + ADR before it lands.**

## DSA / complexity
- `chunk_text`: O(n) over section text; passage count ≈ ⌈chars / max_chars⌉.
- Batched embed: O(N) total, peak ≈ batch_size × dims — **bounded**.
- Parse: optionally release per-page block lists sooner (bounded), if measurement shows need.

## SOLID / patterns
- **SRP:** chunking is its own module; embedding batching is internal to the embedder wrapper.
- **Open/Closed:** `batch_size` is a parameter; chunk thresholds configurable.
- **Wrapper boundary:** chunker is net-new and pure; embedder stays behind `IEmbedder`.
- **Backward-compat:** Step 1 changes no format; Step 2 is additive/optional.

## Backward-compatibility surface
- Step 1: no `.udf`/`UDF_VERSION`/public-API change; net-new `chunking.py`; small/medium docs
  produce a single passage per section → identical vectors today.
- Step 2: additive optional `.udf` field; old files + old readers unaffected.

## Measurement (test-first)
- Peak-RSS test (tracemalloc / RSS) on converting the largest fixture vs a documented budget.
- Retrieval test: a query for content **late** in a giant section is found (fails today).
- Batched-embed test: peak does not scale with N (monkeypatch embedder to record max batch).
