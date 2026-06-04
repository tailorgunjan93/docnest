# Task 4 — Complex Tables · Final Roadmap

Scope = full overhaul, **split into low-risk increments** (protocol: shrink Med/High work).
Each step runs its own mini-cycle: impact → design (ADR if significant) → test-first →
implement → verify (full suite + accuracy) → commit on the task branch. Release batched.

| Step | Area | Risk | Value | Notes |
|---|---|---|---|---|
| **1** | **Row-truncation fix** (`reader`, token-budgeted) | **Low** | **High** | Do first; **re-run the 88-Q accuracy eval** to quantify the gain (targets errors #1/#2). Render-only, no format change. |
| 2 | HTML `rowspan`/`colspan` grid expansion | Low–Med | Med | Self-contained in `html._extract_table`. |
| 3 | PyMuPDF `find_tables` extraction | Med | High | New capability; pairs with the OCR fast path. ADR. |
| 4 | DOCX merged-cell grid + header flatten | Med | Med | Replace consecutive-dedup with positional grid. |
| 5 | XLSX merged cells + multi-table interaction | Med | Med | Weigh `read_only=False` (RAM). ADR. |
| 6 | Hierarchical/multi-row header flattening (cross-parser) | Med | Med | Optional `TableData.header_rows`? (design decision) |

## Sequencing rationale
- Step 1 is the biggest accuracy win at the lowest risk → ship/measure first.
- Steps 2–6 are independent parser improvements; each is gated and reversible.
- Stop/re-prioritise after any step based on the accuracy delta.

## Milestones
- M1: Phase 0 docs approved (this set).
- M2: Step 1 implemented + full suite green + **accuracy re-measured**.
- M3+: Steps 2–6 landed incrementally.
- Final: batched PyPI release (Tasks 1+3+4) — version bump + CHANGELOG.

## Open decisions for owner
1. **Token budget per table** for the reader (default ~1500 chars / ~400 tokens?) and the
   truncation-note wording.
2. **`TableData.header_rows`** — add optional multi-row header field now (Step 6) or flatten only?
3. **XLSX `read_only=False`** for merges — accept higher RAM, or keep read-only + skip XLSX merges?
4. After Step 1, **re-run the full accuracy eval** (needs an API key) to confirm the gain — OK?
