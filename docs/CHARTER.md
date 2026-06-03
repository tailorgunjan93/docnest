# DOCNEST — Project Charter / North Star

> The single source of truth for *why* DocNest exists and *what "done well" means*.
> Every task must trace back to this. A change that does not serve the charter is
> out of scope. Read alongside [DEVELOPMENT_PROTOCOL.md](../DEVELOPMENT_PROTOCOL.md).

## Vision
The document normalization engine RAG has always needed: read a document's **structure**
before its content, so an LLM always receives the *right* context — never blind chunks.
Output a portable, self-contained `.udf` knowledge base.

## Who it's for
AI-first / developer audience building RAG pipelines and tools on top of DocNest
(e.g. the `knovex` desktop app, the `udf-spec` format). Not a consumer end-product.

## Decision filter (the motto)
Every decision is judged against: **Secure · Fast · Reliable · Cost-Effective.**
If a change weakens one of these without a deliberate, recorded trade-off, reconsider it.

## Success Metrics / KPIs (define "done well")
A change is only "green" if it holds ALL of these (see protocol GATE 5):
- **Accuracy:** RAG accuracy on the 88-question / 10-doc / 5-format suite **≥ 9.55/10**
  — never regress.
- **Reliability:** full test suite green; **0 escaped defects**; regression suite only grows.
- **Speed:** warm retrieval ~**1 ms/query**; ingestion predictable.
- **Memory:** large-PDF processing uses **bounded RAM** (scales with chunk size, not
  file size); no OOM.
- **Cost:** ~70% of queries answered with **0 LLM tokens** (Layers 0–1); token use per
  query does not regress.
- **Privacy:** core path (parse → normalise → embed) runs **fully local**, no mandatory
  network calls.

## Product-level non-goals (for now)
- Not a consumer GUI (that's `knovex`).
- No cryptographic provenance / signing in core yet (possible future direction).
- No cloud dependency in the core path.

## Current mission
Make DocNest **robust on everything**. Active hardening order:
1. Complex tables → 2. Image/scanned PDFs → 3. Large PDFs.
