# Task 1 — Path/Schema Compaction · BA / Functional Document

## WHY (the problem)
A `.udf` is a **shareable** artifact (email, USB, S3). Today every `.udf` embeds the
author's **absolute source path** inside `catalogue.json`:

```json
"source": "D:\\Learning\\docnest\\test_docs\\sample_report.md"
```

This leaks private information about the author's machine — **username, directory
layout, operating system** — to anyone who receives the file. It is also **non-portable**
(meaningless on another machine) and is exactly the kind of "dead padding" Ken Alger
flags under *input custody*. It conflicts with the Charter's **Secure** pillar.

> Note (scope honesty): in DocNest this absolute path is **not** sent to the LLM today —
> the reader builds context from `§id` + title + text. So the win here is **privacy +
> portability**, not LLM token savings. The token-padding/header-injection optimisation
> is a *separate* later task (Observer's Tax).

## WHAT (required behaviour)
- **Default:** a newly written `.udf` stores a **compact, non-absolute** source value
  (the file **basename**, e.g. `sample_report.md`) — never a full filesystem path.
- **Opt-in:** a flag (e.g. `include_source_path=True`) lets a user deliberately keep the
  full path for internal use.
- **No behavioural change** to: retrieval results, RAG accuracy, query layers, the HTML
  viewer, or the ability to open/query **existing** `.udf` files.
- **(Related, secondary)** the library index should prefer relative/alias paths over
  absolute ones where possible.

### Acceptance criteria
1. After `docnest convert X`, `catalogue.json`'s `source` contains **no drive letter /
   absolute path** by default (just the basename or a doc_id alias).
2. With the opt-in flag, the full path is preserved (back-compat for power users).
3. Opening and querying a **pre-existing** `.udf` (which still has an absolute path)
   works exactly as before.
4. RAG accuracy suite result is **unchanged** (this task does not touch retrieval).
5. Full test suite green; existing parser `source` tests still green.

### Non-goals
- Not changing parser internals or `RawDocument.source` (parsers legitimately need the
  real path while processing).
- Not changing retrieval, embeddings, or the SQLite engine.
- Not the header-injection / Observer's Tax token work (separate task).

## HOW (functional flow, no implementation detail)
1. User converts a document → DocNest writes the `.udf`.
2. At write time, the source is **sanitised to a portable form** before being stored.
3. The user shares the `.udf`; a recipient inspecting it sees only `sample_report.md`,
   nothing about the author's machine.
4. Opening it anywhere (old or new file) still lists sections, queries, and renders HTML
   identically.

### Edge cases to honour
- Paths with spaces / unicode / no extension.
- Folder conversion (library mode) — same sanitisation applies per document.
- Old `.udf` files with absolute `source` — must remain fully readable.
