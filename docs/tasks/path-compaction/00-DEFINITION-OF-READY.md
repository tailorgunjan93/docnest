# Task 1 — Path/Schema Compaction · Definition of Ready

- **Goal (one sentence):** A shared `.udf` must not embed the author's absolute
  filesystem path; store a compact, portable source value instead — without changing
  retrieval, accuracy, or how old files are read.
- **Traces to Charter:** ✅ **Secure** (no machine/path info leak) and **Reliable/portable**
  output. Aligns with Ken Alger's "input custody / dead-padding" framing.
- **Owner:** Gunjan Tailor. **Priority:** first (Plan A warm-up).
- **Acceptance criteria drafted:** ✅ (see BA doc).
- **Owner gave explicit go:** ✅ ("lets go for ken suggestions").

**DoR GATE: PASSED** → Phase 0 may begin.
