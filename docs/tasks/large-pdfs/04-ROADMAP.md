# Task — Large PDFs · ROADMAP

## Ordered steps
1. **Phase 0** — BA / Dev / QA / Roadmap (this set), grounded in measured doc sizes + code. ✅
2. **Owner gate** — review Phase 0; explicit **go** before code. ⛔ (we are here)
3. **Step 1a — `docnest/chunking.py`** (`chunk_text`, deterministic, net-new). ADR-0007.
   Test-first; imported by nothing → zero blast radius. → owner gate.
4. **Step 1b — batched embedding** in the embedder wrapper / writer (bounded peak memory).
   Test-first (max-batch assertion). → owner gate.
5. **Step 1c — wire passage chunking into the `HybridRetriever` build path** (retrieval.py):
   index passages with parent-section ids; results map back to the section. Improves the
   retrieval/eval path with **no `.udf` change**. Impact/risk pass (Medium — changes retrieval
   build). Test: deep-content recall; full suite. → owner gate.
6. **Memory benchmark** — peak-RSS test on the largest fixture vs a documented budget.
7. **Step 2 (separate task/gate) — persist passage embeddings in `.udf`** (backward-compatible
   optional field) so the reader path benefits. Own impact/risk + ADR + UDF_VERSION decision.

## Dependencies
- Step 1a is standalone. 1b independent. 1c depends on 1a (+ ideally 1b).
- Reuses `IEmbedder` + `HybridRetriever`; `Section`/`TableData` unchanged.

## Milestones
- M1: Phase 0 + ADR-0007.
- M2: chunker (red→green) + batched embed → full suite green (standalone).
- M3: wired into HybridRetriever + deep-content recall test + peak-RSS benchmark.
- M4 (separate): `.udf` passage persistence.

## Risk / impact
- **1a/1b: Low** — net-new / parameter-gated, additive.
- **1c: Medium** — changes the retrieval build path; gated, test-first, regression-first.
- **Step 2: Medium** — `.udf` format addition (backward-compatible); separate gate.
- Honors the bounded-memory NFR (the whole point); verified by a peak-RSS test, not assertion.
