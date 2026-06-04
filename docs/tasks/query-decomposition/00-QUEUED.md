# Task — Multi-aspect Query Decomposition · QUEUED (Phase 0 pending owner go)

> **Status:** Queued — next task per the eval retrospective (Part 8). Phase 0 (BA/Dev/QA
> + Roadmap) to be written when picked up. **Do not start code without owner go.**

## Why (evidence)
The live retrieval-correctness audit (docs/retrospectives/2026-06-03-...md, Part 8) showed
DocNest feeds the correct context ~29/30 on hard PDFs. The **one genuine miss — BIS Q4**
("financial-stability risks relating to asset price volatility, **herding**, **concentration
risk**") — is a **first-stage recall / vocabulary-gap** failure:
- Retrieved §43 (Commercial Real Estate); the answer lives in the **AI chapter (§111–135)**.
- The correct section ranked **below the top-30 pool** → the cross-encoder never sees it →
  **ranker tuning cannot fix it.**
- The query's finance framing dominates; the "AI herding/concentration" aspect is lost;
  the answer is also **spread across multiple sections**.

## What (intended behaviour, to be refined in Phase 0)
- Detect **multi-aspect / multi-part** questions and **decompose** them into aspect
  sub-queries (e.g. "asset price volatility", "herding behaviour", "concentration risk").
- Retrieve **per aspect**, then **merge** candidate sections (union + RRF) so an aspect with
  a distinct vocabulary (the AI chapter) surfaces even when another aspect dominates.
- Deterministic decomposition first (rules/templates over conjunctions, comma-lists,
  "and"/"or", question sub-clauses); LLM-assisted decomposition only as optional augmentation.

### Acceptance criteria (draft)
1. BIS Q4: the AI-chapter section that answers herding/concentration appears in the merged
   top-k (currently absent from top-30).
2. No regression on the ~29/30 questions already retrieving correct context.
3. Deterministic, local-first, behind a wrapper; no `.udf`/API/format change.

## Non-goals
- Replacing the hybrid retriever (BM25+dense is the robust base — research in retrospective).
- Ranker weight tuning (proven wrong tool for this class of miss).

## Secondary lever (separate evaluation)
- Stronger sentence/section embedder than 384-d `all-MiniLM-L6-v2` to bridge semantic gaps
  — weigh against the local-first / dependency / RAM NFR budgets.

## Protocol
Phase 0 (4 docs) → Impact/Risk → Design + ADR → test-first → full regression → owner gate.
Branch off `main` (or current head); never merge without explicit go.
