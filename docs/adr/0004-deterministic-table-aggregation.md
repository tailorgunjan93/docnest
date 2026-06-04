# ADR-0004 — Deterministic table aggregation in the library (not the LLM)

- **Status:** Accepted
- **Date:** 2026-06-04
- **Deciders:** Gunjan Tailor (owner)
- **Related:** docs/retrospectives/2026-06-03-rag-eval-retrospective.md (§5.4, §5.7),
  docs/tasks/table-aggregation/, ADR-0003 (budgeted table rendering)

## Context
The RAG eval showed DocNest retrieves the correct table and places every row in the
prompt, then asks the **LLM** to filter-and-sum. The LLM is unreliable at this: Acme Q8
("total ARR from Enterprise rows = 7,600") returned an **empty answer** at both 1024 and
2048 token caps. Arithmetic and number normalization over structured rows are
**deterministic** problems; trusting a stochastic model with them is the wrong design and
leaves DocNest with no answer when the model fails.

## Decision
Add a pure-Python, dependency-free module `docnest/aggregation.py` that performs
deterministic **sum / count / min / max / avg** over a `TableData` column, with an optional
row filter, plus a robust `parse_number` for messy cells (`$4,050`, `12 550`, `99.97%`,
`1.24 billion`, `5.8x`). It returns a structured `AggregationResult` and **fails closed**
(`ok=False` + reason) rather than guessing. The brain for table math lives **in the
library**; the LLM is reserved for genuine free-text synthesis.

## Consequences
- **Positive:** exact, zero-token, offline answers for aggregation queries; removes a class
  of empty/wrong answers; a stable seam (`TableQuery` → `AggregationResult`) for later
  wiring into the reader query path + query-intent router.
- **Neutral:** net-new file imported by nothing yet → zero blast radius; no `.udf`,
  `UDF_VERSION`, public-API, or PyPI change.
- **Cost:** maintain a deterministic number/unit parser (covered by unit tests).

## Alternatives considered
- **Keep delegating to the LLM** — rejected: proven unreliable (empty answers), non-zero
  token cost, non-deterministic.
- **Add pandas/numpy** — rejected: violates the lazy/pinned/minimal dependency policy and
  local-first NFR for what regex + a linear fold already solve.
- **Swap the retriever (e.g. SPLADE)** — out of scope; retrieval already returns the right
  table. Research (see retrospective) shows hybrid BM25+dense is the robust choice.
