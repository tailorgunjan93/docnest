# DOCNEST — Development Protocol (MANDATORY)

> **READ THIS FIRST, BEFORE ANY CHANGE — even a one-word change.**
> No code is written until every gate below is satisfied. No exceptions.
> Mission: a **robust** DocNest that works on *everything*. Current weak spots to harden:
> **large PDFs, image/scanned PDFs, complex tables.**

This protocol is the contract for how we work on DocNest. It is enforced for every
task. If a step is skipped, the work is not done. Each phase has an explicit **GATE**
that must be green before moving on.

---

## The Golden Rules (non-negotiable)

1. **Understand the requirement first** — in depth, from three lenses (BA, Dev, QA),
   each producing its own document, before any design or code.
2. **Understand the code before you touch it.**
3. **Plan the code before writing it** — what code, where, and why.
4. **Tests come before the fix/feature** (test-first).
5. **Run the FULL suite every cycle** (regression-first; never break what worked).
6. **Never push to `main` directly** — temp branch → prove green → merge → release.
7. **Every external module gets a wrapper** (no third-party calls scattered in core).
8. **Low risk + low impact + all green** is the only path to a "✅ green mark".
9. **The owner signs off every gate** — no phase advances without explicit approval.
10. **No task starts until it is Ready** (Definition of Ready, below).

---

## Project Foundations (read alongside this protocol)

These are the shared "vision" documents. Every task must trace back to them.

- **[Charter / North Star](docs/CHARTER.md)** — vision, audience, the motto as decision
  filter, product-level non-goals, and the **Success Metrics / KPIs** that define
  "done well." A change that does not serve the charter is out of scope.
- **Non-Functional Requirements & Dependency Policy** — the technical bar (below).
- **[Architecture Decision Records](docs/adr/)** — the permanent "why" behind every
  significant technical choice. A significant decision is not done until its ADR exists.

---

## Definition of Ready (DoR) — gate BEFORE Phase 0

A task may not enter Phase 0 until ALL are true:
- [ ] Clear goal stated in one sentence, traceable to the [Charter](docs/CHARTER.md).
- [ ] Owner assigned and priority agreed.
- [ ] Acceptance criteria drafted (what "working" means).
- [ ] Owner has given the explicit **go**.

**GATE (DoR):** all four checked → the task is Ready → Phase 0 may begin.

---

## Non-Functional Requirements & Dependency Policy (the technical bar)

Every change is checked against these; blowing a budget fails the gate.

- **Memory:** large-document processing must use **bounded memory** (peak RAM scales
  with chunk size, not total file size). No OOM / `std::bad_alloc`.
- **Latency:** warm retrieval stays ~1 ms/query; ingestion stays predictable.
- **Privacy / local-first:** the core path (parse → normalise → embed) must work with
  **no mandatory network calls** (local HuggingFace default). Cloud is opt-in only.
- **Dependencies:** minimal and justified; **lazy-imported**; pinned in `pyproject`;
  prefer a stdlib / zero-dep fallback; **every external module sits behind a wrapper.**
- **Compatibility:** never silently break existing `.udf` files, `UDF_VERSION`, or the
  public API. Breaking changes require an ADR + version bump + migration note.

---

## Phase 0 — REQUIREMENTS UNDERSTANDING (in-depth, 3 perspectives + roadmap)
**This is the first thing, always.** Before design, tests, or code, deeply understand
*what is being asked* from three independent viewpoints and write a document for each.
Only after all three exist do we produce the final roadmap.

### 0.1 — Functional Understanding (BUSINESS ANALYST lens) → **BA document**
Capture the requirement as functionality. The document answers:
- **WHY** — the business/user problem and goal.
- **WHAT** — the exact functional behaviour required; user-visible before vs after;
  acceptance criteria; explicit non-goals.
- **HOW** — the functional flow (no implementation detail), edge cases, and the
  user scenarios it must satisfy.

### 0.2 — Technical Understanding (DEVELOPER lens) → **Dev document**
The same requirement, but technical. The document includes:
- End-to-end **reading & understanding of the existing code** the change involves
  (trace data flow across files; name every file/function that could be touched).
- The technical *what* and *how*: current behaviour, where it lives, constraints,
  dependencies, backward-compatibility surface (`.udf` files, `UDF_VERSION`,
  public API, PyPI consumers).

### 0.3 — User/Quality Understanding (QA lens) → **QA document**
The same requirement, from the user's seat and a tester's mind:
- What "working" means to a user; how a user will exercise it.
- The full test thinking: scenarios, edge/negative cases, data variety
  (incl. the hard ones — large PDF, image/scanned PDF, complex table),
  and what would constitute a regression.

### 0.4 — FINAL ROADMAP
Consolidate the three documents into a single sequenced roadmap: ordered steps,
dependencies, milestones, and the risk/impact expectation per step.

**GATE 0:** All three documents (BA, Dev, QA) **and** the final roadmap are written
and agreed. Nothing proceeds until then.

## Phase 1 — IMPACT & RISK ANALYSIS (blast radius)
**Do:** Map every part of the code the change touches or could affect. For each:
note the impact and whether it is breaking. Classify overall **Risk = Low / Med / High**
and **Impact = Low / Med / High**.
- Proceed to build **only if Risk is Low and Impact is Low** (after mitigations).
- If Med/High: shrink the change, add safeguards, or split into smaller steps until Low.
Mark down backward-compatibility concerns (existing `.udf` files, `UDF_VERSION`,
public API signatures, PyPI consumers).
**GATE 1:** Impact map written; risk reduced to Low; backward-compat plan stated.

## Phase 2 — DESIGN (DSA + Architecture)
**Do, in this order:**
1. **DSA pass (efficiency expert):** choose data structures & algorithms for speed and
   low memory. State complexity (time/space) and why it's optimal for the expected
   input sizes (e.g. large PDFs → bounded memory, streaming/chunking).
2. **Senior engineer / architect pass:** how the change stays **SOLID-compliant**;
   which **design pattern** is used and **why**; how to achieve **minimal impact** on
   existing code (additive over destructive; extend interfaces, don't rewrite).
3. **Wrapper rule:** any external/third-party module is accessed only through a
   DocNest wrapper/interface (e.g. an `IParser`, `IEmbedder`, `ILLMProvider`-style
   boundary) — never called directly from core logic.
4. **Code plan:** list exactly which functions/classes/files will be added or edited,
   and the signature of each. No prose-free coding.
**GATE 2:** Written design note: complexity + SOLID/pattern justification + wrapper
boundary + file-by-file code plan. **Any significant decision is recorded as an
[ADR](docs/adr/).**

## Phase 3 — TEST FIRST (manual + automation tester hat)
**Do:** Write tests *before* implementation:
- **Unit** tests for the new/changed units.
- **Integration** tests across the affected modules.
- **Functional** tests for the user-visible behaviour / acceptance criteria.
- **End-to-end** tests (real file in → expected `.udf` / answer out) for the headline
  scenarios, including the hard ones: **large PDF, image/scanned PDF, complex table.**
- Add every reproduced bug as a **regression** test (see Phase 6 defect rules).
Tests must fail first (proving they test the right thing), then pass after the code.
**GATE 3:** New tests exist and currently fail for the right reason.

## Phase 4 — IMPLEMENT
**Do:** Write the code exactly per the Phase 2 plan. Match surrounding style. Keep the
change minimal and behind wrappers.
**GATE 4:** Code compiles/imports; matches the written plan.

## Phase 5 — VERIFY (run the FULL suite every cycle)
**Do:** Run the **entire** test suite (unit + integration + functional + e2e +
regression) on **every** iteration — not just the new tests — to catch collateral
breakage. Maintain a dedicated **regression suite** that only grows.
**GATE 5:** 100% of the suite passes **and the [Charter](docs/CHARTER.md) Success
Metrics are met (no accuracy/latency/memory regression)** → eligible for the **✅ green
mark**.

## Phase 6 — DEFECT PROTOCOL
- **Found during dev (before fixing):** first write failing test cases in **both** the
  **regression** suite **and** the relevant **unit** suite, then fix, then confirm the
  tests pass.
- **Escaped (found after the change shipped):** in addition to fixing, perform a
  **root-cause analysis**: *why didn't dev/testing catch this?* Record the gap and add
  the missing test layer so the class of bug can never escape again.

## Phase 7 — GIT & RELEASE WORKFLOW
1. **Never commit/push directly to `main`.**
2. Create a **temporary branch** for the change.
3. Do the work, run the full suite, get all green there.
4. Only then **merge to `main`**.
5. Bump version + update `CHANGELOG.md`, then cut a **new PyPI release** (`docnest-ai`).
   (Always bump version + changelog before a PyPI release.)

---

## Per-change checklist (paste into every task / PR)

- [ ] Phase 0.1: BA / functional document (why, what, how) written
- [ ] Phase 0.2: Dev / technical document written (incl. code read end-to-end, files listed)
- [ ] Phase 0.3: QA / user document written (scenarios, edge/negative, regression view)
- [ ] Phase 0.4: Final roadmap written (ordered steps, deps, milestones, risk/impact)
- [ ] Phase 1: Impact map written; Risk=Low, Impact=Low; backward-compat plan
- [ ] Phase 2: DSA complexity stated; SOLID/pattern justified; wrappers defined; code plan written
- [ ] Phase 3: Unit + integration + functional + e2e tests written and failing first
- [ ] Phase 4: Code implemented per plan
- [ ] Phase 5: FULL suite run this cycle — all green
- [ ] Phase 6: Any bug → regression + unit tests added (+ RCA if escaped)
- [ ] Phase 7: On temp branch → merged to main on green → version+CHANGELOG → PyPI

## Definition of Done
A change is **done** only when: the three understanding documents + roadmap exist, full
suite green, regression suite extended, design/impact notes recorded, merged from a temp
branch to `main`, and (if releasing) version bumped + CHANGELOG updated + PyPI published.

---

## Current hardening targets (the "works on everything" mission)
These are the known weak spots this protocol is meant to fix carefully:
1. **Large PDFs** — must process with bounded memory, no OOM, no quality loss.
2. **Image / scanned PDFs** — OCR path must reliably extract text.
3. **Complex tables** — merged cells, multi-row headers, multi-table pages must survive
   ingestion without losing column meaning.
Every change toward these must still pass the full regression suite.
