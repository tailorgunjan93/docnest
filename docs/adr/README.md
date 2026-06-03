# Architecture Decision Records (ADRs)

The permanent "why" behind every significant technical decision in DocNest.

**Rule (from [DEVELOPMENT_PROTOCOL.md](../../DEVELOPMENT_PROTOCOL.md) GATE 2):** a
significant decision is not "done" until its ADR exists here.

## What counts as "significant"
- A new module/interface, a new external dependency, or a new wrapper boundary.
- A change to the `.udf` format, `UDF_VERSION`, or the public API.
- A choice of algorithm/data-structure with a real trade-off (speed/memory/accuracy).
- Anything you'd otherwise have to re-explain or re-litigate later.

## How to add one
1. Copy [`0000-template.md`](0000-template.md) to `NNNN-short-title.md` (next number).
2. Fill it in. Keep it short — one decision per record.
3. Link it from the task's Dev document and the PR.

## Index
- 0000 — Template (not a real decision)
- [0001 — Sanitise `source` at the write boundary (privacy-by-default)](0001-sanitise-source-at-write-boundary.md) — Accepted
