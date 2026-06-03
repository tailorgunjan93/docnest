# DocNest — project instructions

## ⛔ STOP — read the Development Protocol before ANY change

**Before writing or editing even one word of code, read and follow
[DEVELOPMENT_PROTOCOL.md](DEVELOPMENT_PROTOCOL.md).** It is mandatory and gated.
Read it alongside the **[Charter / North Star](docs/CHARTER.md)** (vision + success
metrics) and the **[ADRs](docs/adr/)** (the permanent "why").

**Before any task starts:** it must pass the **Definition of Ready** and you (the owner)
must give an explicit **go**. **You sign off every phase gate** — nothing advances without it.
Every change is checked against the **NFR budgets** (bounded memory, ~1 ms warm query,
local-first, deps lazy + wrapped + pinned) and must not regress the Charter Success Metrics.

Quick gist (full rules + gates live in the protocol doc):

0. **Understand the requirement FIRST (Phase 0)** — in depth, from 3 lenses, each a written document, then a roadmap:
   - **BA / functional doc** — why, what, how (functional; acceptance criteria; non-goals).
   - **Dev / technical doc** — technical what/how, incl. reading the code end-to-end + backward-compat surface.
   - **QA / user doc** — what "working" means to a user; scenarios, edge/negative, regression view.
   - **Final roadmap** — ordered steps, deps, milestones, risk/impact. Nothing proceeds until all 4 exist.
1. **Plan code before writing** — what code, where, why (no prose-free coding).
2. **Impact & risk map** — list every affected area; proceed only if Risk=Low & Impact=Low; keep backward compatibility (`.udf` files, `UDF_VERSION`, public API, PyPI).
3. **DSA + architecture pass** — state complexity; justify SOLID compliance + design pattern; minimal impact; **every external module behind a wrapper**.
4. **Test first** — unit + integration + functional + end-to-end; tests fail first, then pass.
5. **Run the FULL suite every cycle** — regression-first; never break what worked. The regression suite only grows.
6. **Defects** — found-in-dev → add regression + unit tests then fix; escaped → also do root-cause analysis on why it wasn't caught.
7. **Git** — never push to `main` directly; temp branch → all green → merge → bump version + CHANGELOG → new PyPI (`docnest-ai`).
8. Only **all-green** earns the ✅ green mark.

**Mission:** robust DocNest that works on everything. Active hardening targets:
**large PDFs, image/scanned PDFs, complex tables.**

## Repo facts
- Library: `docnest/` — see [DEVELOPMENT_PROTOCOL.md](DEVELOPMENT_PROTOCOL.md) for the workflow.
- Install: `pip install docnest-ai`. Motto: Secure · Fast · Reliable · Cost-Effective.
